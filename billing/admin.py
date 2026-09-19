from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from unfold.admin import ModelAdmin

from core.models import Notification, Resort
from core.notifications import notify_user
from core.permissions import RoleBasedAdminMixin, SupervisorAdminMixin
from .models import Charge, PaymentDeferral, PaymentPlan, PaymentPlanInstallment


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


@admin.register(PaymentDeferral)
class PaymentDeferralAdmin(RoleBasedAdminMixin, ModelAdmin):
    """
    Mostly a read-only audit log (append-only "legal record" of deferred due
    dates). Staff use "Add" directly for the >3-day case the self-service
    app endpoint refuses to create — save_model forces STAFF_APPROVED and
    stamps decided_by, mirroring TeamMembershipRequestAdmin.save_model.
    """
    required_roles = ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]
    list_display = ("id", "charge", "requested_by", "deferred_to", "status", "decided_by", "decided_at", "created_at")
    list_filter = ("status",)
    search_fields = ("charge__unit__unit_key", "requested_by__phone")
    autocomplete_fields = ("charge", "requested_by")
    readonly_fields = ("status", "decided_by", "decided_at", "created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(charge__resort=request.user.resort)
        return qs

    def save_model(self, request, obj, form, change):
        # Staff picks which of the unit's owner/tenant this is for via the
        # requested_by autocomplete field — never guessed, since a unit can
        # have both an Owner and a Tenant linked (see Tenant role work).
        if not change:
            obj.status = PaymentDeferral.Status.STAFF_APPROVED
            obj.decided_by = request.user
            obj.decided_at = timezone.now()
        super().save_model(request, obj, form, change)


def _is_payment_plan_manager(request):
    return request.user.is_superuser or getattr(request.user, "role", "") in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]


@admin.action(description="Approve selected payment plans")
def approve_payment_plans(modeladmin, request, queryset):
    if not _is_payment_plan_manager(request):
        raise PermissionDenied("You are not allowed to approve payment plans.")
    for plan in queryset:
        plan.approve(request.user)
        notify_user(
            plan.requested_by,
            title="Payment Plan Approved",
            body=f"Your payment plan for {plan.charge.unit.unit_key} was approved.",
            notif_type=Notification.Type.PAYMENT_PLAN_DECIDED,
            data={"type": "payment_plan_decided", "plan_id": plan.id, "status": "APPROVED"},
        )


@admin.action(description="Reject selected payment plans")
def reject_payment_plans(modeladmin, request, queryset):
    if not _is_payment_plan_manager(request):
        raise PermissionDenied("You are not allowed to reject payment plans.")
    for plan in queryset:
        plan.reject(request.user)
        notify_user(
            plan.requested_by,
            title="Payment Plan Rejected",
            body=f"Your payment plan for {plan.charge.unit.unit_key} was rejected.",
            notif_type=Notification.Type.PAYMENT_PLAN_DECIDED,
            data={"type": "payment_plan_decided", "plan_id": plan.id, "status": "REJECTED"},
        )


class PaymentPlanInstallmentInline(admin.TabularInline):
    model = PaymentPlanInstallment
    extra = 0


@admin.register(PaymentPlan)
class PaymentPlanAdmin(RoleBasedAdminMixin, ModelAdmin):
    required_roles = ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]
    list_display = ("id", "charge", "requested_by", "status", "requested_at", "decided_by", "decided_at")
    list_filter = ("status",)
    search_fields = ("charge__unit__unit_key", "requested_by__phone")
    inlines = (PaymentPlanInstallmentInline,)
    actions = [approve_payment_plans, reject_payment_plans]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(charge__resort=request.user.resort)
        return qs