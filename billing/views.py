from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from core.models import OwnerUnit
from users.models import User
from .models import Charge
from .serializers import ChargeSerializer


class OwnerChargeListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChargeSerializer

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
            .select_related("unit")
            .order_by("-year", "-month", "-id")
        )

        # optional filters
        unit = self.request.query_params.get("unit")
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        ctype = self.request.query_params.get("type")

        if unit:
            qs = qs.filter(unit_id=unit)
        if year:
            qs = qs.filter(year=int(year))
        if month:
            qs = qs.filter(month=int(month))
        if ctype:
            qs = qs.filter(type=ctype)

        return qs