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
from .models import Charge, PaymentDeferral, PaymentPlan
from collections_app.models import Payment
from .serializers import (
    ChargeSerializer,
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

        unit_ids = OwnerUnit.objects.filter(owner=user).values_list("unit_id", flat=True)

        qs = (
            Charge.objects.filter(
                unit_id__in=unit_ids,
                status=Charge.Status.PUBLISHED,
            )
            .select_related("unit", "resort")
            .prefetch_related("allocations")
            .order_by("-year", "-month", "-id")
        )

        # A Tenant only deals with utility bills, never the owner's annual
        # maintenance/service charges.
        if user.role == User.Role.TENANT:
            qs = qs.filter(type__in=[Charge.Type.ELECTRICITY, Charge.Type.WATER])

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

        floor_q = _lease_floor_q(user, unit_ids)
        if floor_q is not None:
            qs = qs.filter(floor_q)

        return qs


class OwnerPaymentHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentHistorySerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if user.role != User.Role.OWNER:
            raise PermissionDenied("Owners only")

        unit_ids = OwnerUnit.objects.filter(owner=user).values_list("unit_id", flat=True)

        qs = (
            Payment.objects.filter(unit_id__in=unit_ids)
            .select_related("unit", "resort")
            .prefetch_related("allocations__charge")
            .order_by("-paid_at", "-id")
        )

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