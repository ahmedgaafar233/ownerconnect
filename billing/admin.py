from django.contrib import admin
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from unfold.admin import ModelAdmin

from core.models import Resort
from core.permissions import SupervisorAdminMixin
from .models import Charge


@admin.action(description="Publish selected charges")
def publish_charges(modeladmin, request, queryset):
    # Only Financial Manager+ can publish
    if not request.user.is_superuser and getattr(request.user, "role", "") not in [
        "FINANCIAL_MANAGER", "GENERAL_MANAGER"
    ]:
        from django.contrib import messages
        messages.error(request, "You do not have permission to publish charges.")
        return
    queryset.update(
        status=Charge.Status.PUBLISHED,
        approved_by=request.user,
        approved_at=timezone.now(),
    )


@admin.register(Charge)
class ChargeAdmin(SupervisorAdminMixin, ModelAdmin):
    """
    Supervisor+ can view charges.
    Financial Manager+ can add/change/delete/publish.
    """
    list_display = (
        "id", "resort", "unit", "type", "year", "month",
        "amount", "paid_total", "remaining", "status", "approved_at"
    )
    list_filter = ("resort", "status", "type", "year")
    search_fields = ("unit__unit_key", "unit__building_no", "unit__unit_no", "notes")
    actions = [publish_charges]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Auto-select first resort as default."""
        if db_field.name == "resort":
            first_resort = Resort.objects.first()
            if first_resort:
                kwargs["initial"] = first_resort.pk
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]

    def get_queryset(self, request):
        # Row-level fix: SupervisorAdminMixin only gates which roles may open
        # this admin at all — it never scoped rows by resort, so any
        # supervisor/FM/GM could browse and export every resort's charges.
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(resort=request.user.resort)
        return qs.annotate(
            _paid_total=Coalesce(
                Sum("allocations__amount"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )

    @admin.display(description="Paid")
    def paid_total(self, obj):
        return obj._paid_total

    @admin.display(description="Remaining")
    def remaining(self, obj):
        return obj.amount - obj._paid_total