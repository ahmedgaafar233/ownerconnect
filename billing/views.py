from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination

from core.models import OwnerUnit
from users.models import User
from .models import Charge
from collections_app.models import Payment
from .serializers import ChargeSerializer, PaymentHistorySerializer


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
        if user.role != User.Role.OWNER:
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