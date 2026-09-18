from rest_framework import serializers
from .models import Charge
from collections_app.models import Payment, PaymentAllocation


class ChargeSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    resort_name = serializers.CharField(source="resort.name", read_only=True)
    paid_amount = serializers.DecimalField(source="total_paid", max_digits=12, decimal_places=2, read_only=True)
    remaining_balance = serializers.DecimalField(source="balance", max_digits=12, decimal_places=2, read_only=True)
    is_paid = serializers.BooleanField(source="is_fully_paid", read_only=True)

    class Meta:
        model = Charge
        fields = (
            "id",
            "unit",
            "unit_key",
            "resort",
            "resort_name",
            "year",
            "month",
            "type",
            "amount",
            "paid_amount",
            "remaining_balance",
            "is_paid",
            "notes",
            "status",
            "approved_at",
            "created_at",
        )


class PaymentAllocationSerializer(serializers.ModelSerializer):
    charge_type = serializers.CharField(source="charge.type", read_only=True)
    charge_year = serializers.IntegerField(source="charge.year", read_only=True)
    charge_month = serializers.IntegerField(source="charge.month", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = (
            "id",
            "charge",
            "charge_type",
            "charge_year",
            "charge_month",
            "amount",
            "created_at",
        )


class PaymentHistorySerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    resort_name = serializers.CharField(source="resort.name", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "unit",
            "unit_key",
            "resort",
            "resort_name",
            "receipt_no",
            "total_amount",
            "paid_at",
            "notes",
            "allocations",
            "created_at",
        )