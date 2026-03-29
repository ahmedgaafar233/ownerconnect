from rest_framework import serializers
from .models import Charge


class ChargeSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)

    class Meta:
        model = Charge
        fields = (
            "id",
            "unit",
            "unit_key",
            "year",
            "month",
            "type",
            "amount",
            "notes",
            "status",
            "approved_at",
            "created_at",
        )