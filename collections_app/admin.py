from decimal import Decimal

from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils.html import format_html

from billing.models import Charge
from core.permissions import SupervisorAdminMixin
from .models import Payment, PaymentAllocation


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    autocomplete_fields = ("charge",)


@admin.action(description="Auto allocate FIFO (oldest first) for selected payments")
def auto_allocate_fifo(modeladmin, request, queryset):
    ok = 0
    for payment in queryset:
        with transaction.atomic():
            allocated = payment.allocations.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
            remaining_to_allocate = payment.total_amount - allocated
            if remaining_to_allocate <= 0:
                continue

            charges = (
                Charge.objects
                .filter(unit=payment.unit, status=Charge.Status.PUBLISHED)
                .annotate(
                    paid=Coalesce(
                        Sum("allocations__amount"),
                        Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )
                .annotate(rem=F("amount") - F("paid"))
                .filter(rem__gt=0)
                .order_by("year", F("month").asc(nulls_last=True), "id")
            )

            for c in charges:
                if remaining_to_allocate <= 0:
                    break
                take = c.rem if c.rem < remaining_to_allocate else remaining_to_allocate
                PaymentAllocation.objects.create(payment=payment, charge=c, amount=take)
                remaining_to_allocate -= take

        ok += 1

    messages.success(request, f"Auto allocated FIFO for {ok} payment(s).")


@admin.register(Payment)
class PaymentAdmin(SupervisorAdminMixin, admin.ModelAdmin):
    """Supervisor+ can view payments. FM+ can add/change."""
    list_display = ("id", "resort", "unit", "receipt_no", "total_amount", "allocated_total", "paid_at", "created_by", "receipt_pdf_link")
    list_filter = ("resort",)
    search_fields = ("receipt_no", "unit__unit_key", "unit__building_no", "unit__unit_no")
    autocomplete_fields = ("unit",)
    readonly_fields = ("receipt_pdf_link",)
    inlines = (PaymentAllocationInline,)
    actions = [auto_allocate_fifo]

    @admin.display(description="Receipt PDF")
    def receipt_pdf_link(self, obj):
        if not obj.receipt_pdf:
            return "—"
        return format_html('<a href="{}" target="_blank">تحميل الإيصال</a>', obj.receipt_pdf.url)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in [
            "SUPERVISOR", "FINANCIAL_MANAGER", "GENERAL_MANAGER"
        ]

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in [
            "FINANCIAL_MANAGER", "GENERAL_MANAGER"
        ]

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in [
            "FINANCIAL_MANAGER", "GENERAL_MANAGER"
        ]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user 
        if obj.unit_id and not obj.resort_id:
            obj.resort = obj.unit.resort
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        # Row-level fix: same gap as ChargeAdmin — any supervisor/FM/GM could
        # previously browse every resort's payments, not just their own.
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(resort=request.user.resort)
        return qs.annotate(
            _allocated=Coalesce(
                Sum("allocations__amount"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )

    @admin.display(description="Allocated")
    def allocated_total(self, obj):
        return obj._allocated
