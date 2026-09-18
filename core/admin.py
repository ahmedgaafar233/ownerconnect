from django.contrib import admin
from django.db.models import Sum, Q, F
from django.utils.translation import gettext_lazy as _
from .models import Resort, Unit, OwnerUnit
from core.permissions import GeneralManagerAdminMixin


class HasBalanceFilter(admin.SimpleListFilter):
    title = _("Balance Status")
    parameter_name = "has_balance"

    def lookups(self, request, model_admin):
        return (
            ("1", _("Has Outstanding Balance")),
            ("0", _("Paid in Full")),
        )

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.annotate(
                total_debt=Sum('charges__amount', filter=Q(charges__status='PUBLISHED')),
                total_paid=Sum('charges__allocations__amount')
            ).filter(total_debt__gt=F('total_paid'))
        if self.value() == "0":
            return queryset.annotate(
                total_debt=Sum('charges__amount', filter=Q(charges__status='PUBLISHED')),
                total_paid=Sum('charges__allocations__amount')
            ).filter(Q(total_debt__lte=F('total_paid')) | Q(total_debt__isnull=True))
        return queryset


@admin.register(Resort)
class ResortAdmin(admin.ModelAdmin):
    """Only superusers can manage resorts."""
    list_display = ("id", "name", "is_active", "created_at")
    search_fields = ("name",)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return request.user.is_superuser


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    """
    All staff can view units.
    Only GM+ can edit.
    """
    list_display = ("id", "resort", "unit_key", "building_no", "unit_no", "is_active")
    list_filter = ("resort", "is_active", HasBalanceFilter)
    search_fields = ("unit_key", "building_no", "unit_no")
    ordering = ("building_no", "unit_no")

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["GENERAL_MANAGER"]

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["GENERAL_MANAGER"]

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        # Row-level fix: has_view/has_module_permission above only gate WHICH
        # roles may open this admin at all — they never scoped rows by
        # resort, so any staff member could browse/search every resort's
        # units. Non-superusers now only ever see their own resort's units.
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(resort=request.user.resort)


@admin.register(OwnerUnit)
class OwnerUnitAdmin(GeneralManagerAdminMixin, admin.ModelAdmin):
    """GM+ can view; only superuser can add/change/delete."""
    list_display = ("id", "owner", "unit", "total_debt", "total_paid", "remaining_balance", "created_at")
    list_filter = ("unit__resort",)
    search_fields = ("owner__phone", "unit__unit_key")
    autocomplete_fields = ("owner", "unit")

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["GENERAL_MANAGER", "FINANCIAL_MANAGER"]

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["GENERAL_MANAGER", "FINANCIAL_MANAGER"]

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") == "GENERAL_MANAGER"

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        # Row-level fix: same gap as UnitAdmin — GM/FM could see every
        # resort's owner-unit links, not just their own.
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(unit__resort=request.user.resort)

    def total_debt(self, obj):
        return obj.owner.total_debt

    def total_paid(self, obj):
        return obj.owner.total_paid

    def remaining_balance(self, obj):
        return obj.owner.remaining_balance