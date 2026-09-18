from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import OwnerUnit
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


def _accessible_charge_or_404(user, charge_id):
    """
    Shared ownership + Tenant-charge-type resolution, matching
    OwnerChargeListView.get_queryset exactly (unit_ids via OwnerUnit, Tenant
    restricted to utility charges) — used by both ChargeDeferView and
    PaymentPlanListCreateView so a Tenant can't defer/plan a maintenance
    charge just by knowing its id.
    """
    unit_ids = OwnerUnit.objects.filter(owner=user).values_list("unit_id", flat=True)
    qs = Charge.objects.filter(unit_id__in=unit_ids)
    if user.role == User.Role.TENANT:
        qs = qs.filter(type__in=[Charge.Type.ELECTRICITY, Charge.Type.WATER])
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

        try:
            from core.tasks import send_fcm_notification_task
            send_fcm_notification_task.delay(
                user_id=user.id,
                title="Payment Deferred",
                body=f"Your payment for {charge.unit.unit_key} was deferred to {deferral.deferred_to}.",
                data={"type": "payment_deferred", "charge_id": charge.id},
            )
        except Exception:
            pass

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