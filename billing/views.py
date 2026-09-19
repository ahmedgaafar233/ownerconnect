from decimal import Decimal

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Notification, OwnerUnit
from core.notifications import notify_unit_counterparts, notify_user
from users.models import User
from .models import Charge, ClearanceStatement, PaymentDeferral, PaymentPlan
from .receipts import generate_clearance_pdf
from collections_app.models import Payment
from .serializers import (
    ChargeSerializer,
    ClearanceStatementSerializer,
    PaymentDeferralSerializer,
    PaymentHistorySerializer,
    PaymentPlanRequestSerializer,
    PaymentPlanSerializer,
)


def _lease_floor_q(user, unit_ids):
    """
    For a Tenant, restricts each unit to charges dated on/after that unit's
    lease_start_date — units with no lease_start_date set stay unrestricted
    (so existing pilot data isn't silently broken). Returns None when no
    floor applies at all (Owner, or no lease dates set on any unit).
    """
    if user.role != User.Role.TENANT:
        return None

    lease_rows = list(OwnerUnit.objects.filter(owner=user, unit_id__in=unit_ids).exclude(lease_start_date=None))
    if not lease_rows:
        return None

    restricted_unit_ids = {r.unit_id for r in lease_rows}
    unrestricted_unit_ids = set(unit_ids) - restricted_unit_ids

    floor_q = Q()
    for r in lease_rows:
        floor_q |= Q(unit_id=r.unit_id) & (
            Q(year__gt=r.lease_start_date.year)
            | Q(year=r.lease_start_date.year, month__gte=r.lease_start_date.month)
            | Q(year=r.lease_start_date.year, month__isnull=True)
        )
    if unrestricted_unit_ids:
        floor_q |= Q(unit_id__in=unrestricted_unit_ids)
    return floor_q


def _accessible_charges_qs(user):
    """
    Base PUBLISHED-charge queryset for OWNER/TENANT — the shared
    unit_ids/TENANT-utility-type/lease-floor resolution used by both
    OwnerChargeListView and ChargeSummaryView, so the two can never drift
    apart (a Tenant's combined total must respect the exact same
    restrictions as their charge list).
    """
    unit_ids = OwnerUnit.objects.filter(owner=user).values_list("unit_id", flat=True)
    qs = Charge.objects.filter(unit_id__in=unit_ids, status=Charge.Status.PUBLISHED)
    if user.role == User.Role.TENANT:
        qs = qs.filter(type__in=[Charge.Type.ELECTRICITY, Charge.Type.WATER])
    floor_q = _lease_floor_q(user, unit_ids)
    if floor_q is not None:
        qs = qs.filter(floor_q)
    return qs, unit_ids


def _accessible_charges_qs_for_unit(user, unit_id):
    """
    Same accessible-charges resolution as _accessible_charges_qs, narrowed
    to one unit — used by the clearance statement so it can never surface a
    charge type or pre-lease period a Tenant can't otherwise see, and 404s
    outright if the user has no OwnerUnit link to that unit at all.
    """
    if not OwnerUnit.objects.filter(owner=user, unit_id=unit_id).exists():
        from django.http import Http404
        raise Http404("Unit not found")
    qs, _unit_ids = _accessible_charges_qs(user)
    return qs.filter(unit_id=unit_id)


def _accessible_charge_or_404(user, charge_id):
    """
    Shared ownership + Tenant-charge-type/lease-date resolution, matching
    OwnerChargeListView.get_queryset exactly (unit_ids via OwnerUnit, Tenant
    restricted to utility charges + their own lease_start_date floor) — used
    by both ChargeDeferView and PaymentPlanListCreateView so a Tenant can't
    defer/plan a maintenance or pre-lease charge just by knowing its id.
    """
    unit_ids = OwnerUnit.objects.filter(owner=user).values_list("unit_id", flat=True)
    qs = Charge.objects.filter(unit_id__in=unit_ids)
    if user.role == User.Role.TENANT:
        qs = qs.filter(type__in=[Charge.Type.ELECTRICITY, Charge.Type.WATER])
        floor_q = _lease_floor_q(user, unit_ids)
        if floor_q is not None:
            qs = qs.filter(floor_q)
    return get_object_or_404(qs, id=charge_id)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100


class OwnerChargeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChargeSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")

        qs, _unit_ids = _accessible_charges_qs(user)
        qs = (
            qs.select_related("unit", "resort")
            .prefetch_related("allocations")
            .order_by("-year", "-month", "-id")
        )

        unit = self.request.query_params.get("unit")
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        ctype = self.request.query_params.get("type")
        unpaid_only = self.request.query_params.get("unpaid_only")

        if unit:
            qs = qs.filter(unit_id=unit)
        if year:
            qs = qs.filter(year=int(year))
        if month:
            qs = qs.filter(month=int(month))
        if ctype:
            qs = qs.filter(type=ctype)

        return qs


class OwnerPaymentHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentHistorySerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        # A Payment belongs to a unit, not a specific person — whoever is
        # OwnerUnit-linked to that unit (Owner or Tenant) sees it, matching
        # the charges list's own unit_ids scoping. No extra Tenant filtering
        # needed here: unlike Charge, Payment has no type of its own.
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")

        unit_ids = OwnerUnit.objects.filter(owner=user).values_list("unit_id", flat=True)

        qs = (
            Payment.objects.filter(unit_id__in=unit_ids)
            .select_related("unit", "resort")
            .prefetch_related("allocations__charge")
            .order_by("-paid_at", "-id")
        )

        unit = self.request.query_params.get("unit")
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")

        if unit:
            qs = qs.filter(unit_id=unit)
        if year:
            qs = qs.filter(paid_at__year=int(year))
        if month:
            qs = qs.filter(paid_at__month=int(month))

        return qs


class ChargeSummaryView(APIView):
    """
    Combined total across every unit the caller can see, plus a per-unit
    breakdown — for an Owner/Tenant with more than one unit, there was no
    aggregate view before this. Reuses _accessible_charges_qs so a Tenant's
    total respects the exact same utility-type + lease-floor restrictions
    as their charge list, never the unscoped User.total_debt/total_paid
    model properties (which predate and ignore both).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")

        qs, _unit_ids = _accessible_charges_qs(user)
        charges = qs.select_related("unit").prefetch_related("allocations")

        total_due = Decimal("0.00")
        total_paid = Decimal("0.00")
        by_unit = {}

        for charge in charges:
            # Summed from the already-prefetched allocations, not
            # charge.total_paid/.balance — those properties re-query via
            # .aggregate() per charge, which would be an N+1 here.
            paid = sum((a.amount for a in charge.allocations.all()), Decimal("0.00"))
            remaining = charge.amount - paid
            total_due += charge.amount
            total_paid += paid

            entry = by_unit.setdefault(
                charge.unit_id,
                {"unit": charge.unit_id, "unit_key": charge.unit.unit_key, "remaining": Decimal("0.00")},
            )
            entry["remaining"] += remaining

        return Response({
            "total_due": str(total_due),
            "total_paid": str(total_paid),
            "total_remaining": str(total_due - total_paid),
            "by_unit": [
                {"unit": v["unit"], "unit_key": v["unit_key"], "remaining": str(v["remaining"])}
                for v in by_unit.values()
            ],
        })


class ClearanceGenerateView(APIView):
    """
    Generates a point-in-time "مخالصة" (clearance statement) PDF for one
    unit: every accessible charge from the requester's lease_start_date up
    to a chosen as_of_date (default today), confirming a zero balance or
    listing what's still outstanding. Reuses _accessible_charges_qs_for_unit
    so it never shows a Tenant a charge type or pre-lease period they
    couldn't otherwise see. Unlike a payment receipt, each request creates
    its own new stored record rather than being capped at one per lease.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")

        unit_id = request.data.get("unit")
        if not unit_id:
            return Response({"detail": "unit is required."}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.localdate()
        as_of_raw = request.data.get("as_of_date")
        if as_of_raw:
            try:
                as_of_date = timezone.datetime.strptime(as_of_raw, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "as_of_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
            if as_of_date > today:
                return Response({"detail": "as_of_date cannot be in the future."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            as_of_date = today

        qs = _accessible_charges_qs_for_unit(user, unit_id)
        qs = qs.filter(
            Q(year__lt=as_of_date.year)
            | Q(year=as_of_date.year, month__isnull=True)
            | Q(year=as_of_date.year, month__lte=as_of_date.month)
        )
        charges = list(qs.select_related("unit").prefetch_related("allocations").order_by("year", "month", "id"))

        total_due = Decimal("0.00")
        total_paid = Decimal("0.00")
        for charge in charges:
            paid = sum((a.amount for a in charge.allocations.all()), Decimal("0.00"))
            total_due += charge.amount
            total_paid += paid
        total_remaining = total_due - total_paid

        lease_row = OwnerUnit.objects.filter(owner=user, unit_id=unit_id).first()

        statement = ClearanceStatement.objects.create(
            unit_id=unit_id,
            requested_by=user,
            period_start=lease_row.lease_start_date if lease_row else None,
            as_of_date=as_of_date,
            total_due=total_due,
            total_paid=total_paid,
            total_remaining=total_remaining,
            is_clear=total_remaining <= 0,
        )
        generate_clearance_pdf(statement, charges)

        return Response(
            ClearanceStatementSerializer(statement, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ClearanceListView(generics.ListAPIView):
    """History of previously generated clearance statements, so a
    tenant/owner can find one they already generated again later."""
    permission_classes = [IsAuthenticated]
    serializer_class = ClearanceStatementSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")

        qs = ClearanceStatement.objects.filter(requested_by=user).select_related("unit")
        unit = self.request.query_params.get("unit")
        if unit:
            qs = qs.filter(unit_id=unit)
        return qs


class ChargeDeferView(APIView):
    """
    Self-service deferral, capped at 3 days from today (PaymentDeferralSerializer
    enforces this). Anything longer is rejected outright — the app never
    queues a request for that; the accountant enters it directly via admin.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")

        charge = _accessible_charge_or_404(user, pk)

        serializer = PaymentDeferralSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deferral = PaymentDeferral.objects.create(
            charge=charge,
            requested_by=user,
            deferred_to=serializer.validated_data["deferred_to"],
            status=PaymentDeferral.Status.AUTO_APPROVED,
            decided_by=user,
            decided_at=timezone.now(),
        )

        notify_user(
            user,
            title="Payment Deferred",
            body=f"Your payment for {charge.unit.unit_key} was deferred to {deferral.deferred_to}.",
            notif_type=Notification.Type.PAYMENT_DEFERRED,
            data={"type": "payment_deferred", "charge_id": charge.id},
        )
        actor_label = user.fullname or user.phone
        notify_unit_counterparts(
            charge.unit,
            acting_user=user,
            title="Unit Payment Deferred",
            body=f"{actor_label} deferred a payment for unit {charge.unit.unit_key} to {deferral.deferred_to}.",
            notif_type=Notification.Type.UNIT_ACTIVITY,
            data={"type": "unit_payment_deferred", "charge_id": charge.id},
        )

        return Response(PaymentDeferralSerializer(deferral).data, status=status.HTTP_201_CREATED)


class PaymentPlanListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PaymentPlanRequestSerializer
        return PaymentPlanSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")
        return (
            PaymentPlan.objects.filter(requested_by=user)
            .select_related("charge")
            .prefetch_related("installments")
            .order_by("-requested_at")
        )

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            raise PermissionDenied("Owners only")
        charge = _accessible_charge_or_404(user, serializer.validated_data["charge"].id)
        serializer.save(requested_by=user, charge=charge)