from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from .models import Charge, ClearanceStatement, PaymentDeferral, PaymentPlan, PaymentPlanInstallment
from collections_app.models import Payment, PaymentAllocation


class PaymentDeferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDeferral
        fields = ("id", "charge", "deferred_to", "status", "decided_by", "decided_at", "created_at")
        # `charge` is resolved from the URL in ChargeDeferView, never from
        # the request body — only `deferred_to` is actually validated there.
        read_only_fields = ("charge", "status", "decided_by", "decided_at", "created_at")

    def validate_deferred_to(self, value):
        today = timezone.localdate()
        if value <= today:
            raise serializers.ValidationError("Deferred date must be in the future.")
        if value > today + timedelta(days=3):
            raise serializers.ValidationError(
                "Self-service deferral is limited to 3 days. Please contact the resort's accountant for longer."
            )
        return value


class ChargeSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    resort_name = serializers.CharField(source="resort.name", read_only=True)
    paid_amount = serializers.DecimalField(source="total_paid", max_digits=12, decimal_places=2, read_only=True)
    remaining_balance = serializers.DecimalField(source="balance", max_digits=12, decimal_places=2, read_only=True)
    is_paid = serializers.BooleanField(source="is_fully_paid", read_only=True)
    active_deferral = PaymentDeferralSerializer(read_only=True)

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
            "active_deferral",
        )


class PaymentPlanInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentPlanInstallment
        fields = ("id", "due_date", "amount", "is_paid")


class PaymentPlanSerializer(serializers.ModelSerializer):
    installments = PaymentPlanInstallmentSerializer(many=True, read_only=True)
    unit_key = serializers.CharField(source="charge.unit.unit_key", read_only=True)

    class Meta:
        model = PaymentPlan
        fields = (
            "id",
            "charge",
            "unit_key",
            "status",
            "requested_at",
            "decided_by",
            "decided_at",
            "decision_note",
            "installments",
        )
        read_only_fields = ("status", "requested_at", "decided_by", "decided_at", "decision_note")


class PaymentPlanRequestSerializer(serializers.ModelSerializer):
    installments = PaymentPlanInstallmentSerializer(many=True)

    class Meta:
        model = PaymentPlan
        fields = ("id", "charge", "installments")

    def validate_installments(self, value):
        if not value:
            raise serializers.ValidationError("At least one installment is required.")
        return value

    def create(self, validated_data):
        installments_data = validated_data.pop("installments")
        plan = PaymentPlan.objects.create(**validated_data)
        for installment in installments_data:
            PaymentPlanInstallment.objects.create(plan=plan, **installment)
        return plan


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
    receipt_pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id",
            "unit",
            "unit_key",
            "resort",
            "resort_name",
            "receipt_no",
            "receipt_pdf_url",
            "total_amount",
            "paid_at",
            "notes",
            "allocations",
            "created_at",
        )

    def get_receipt_pdf_url(self, obj):
        if not obj.receipt_pdf:
            return None
        # Points at the authenticated download view, never the raw /media/
        # path — that path is no longer served publicly (see
        # PaymentReceiptDownloadView).
        request = self.context.get("request")
        path = reverse("payment_receipt_download", args=[obj.id])
        return request.build_absolute_uri(path) if request else path


class ClearanceStatementSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = ClearanceStatement
        fields = (
            "id",
            "unit",
            "unit_key",
            "period_start",
            "as_of_date",
            "total_due",
            "total_paid",
            "total_remaining",
            "is_clear",
            "pdf_url",
            "created_at",
        )
        read_only_fields = fields

    def get_pdf_url(self, obj):
        if not obj.pdf:
            return None
        request = self.context.get("request")
        path = reverse("clearance_pdf_download", args=[obj.id])
        return request.build_absolute_uri(path) if request else path