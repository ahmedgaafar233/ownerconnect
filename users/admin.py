from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from core.models import OwnerUnit, Resort
from core.permissions import RoleBasedAdminMixin
from users.models import User
from .models import Team, TeamMembership, TeamMembershipRequest


def _format_currency(value):
    try:
        return f"EGP {value:,.2f}"
    except Exception:
        return f"EGP {value}"


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


class OwnerUnitInline(admin.TabularInline):
    model = OwnerUnit
    extra = 0
    autocomplete_fields = ("unit",)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    
    ordering = ("id",)
    list_display = ("phone", "role", "is_staff", "is_active", "total_debt_display", "total_paid_display", "remaining_balance_display")
    list_filter = ("role", "is_active")  # Removed resort from filter
    search_fields = ("phone",)
    inlines = (OwnerUnitInline,)

    readonly_fields = ("owner_statement",)

    # Removed resort from fieldsets
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Role", {"fields": ("role", "resort")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Owner Statement", {"fields": ("owner_statement",)}),
    )
    # Removed resort from add_fieldsets
    add_fieldsets = (
        (None, {"fields": ("phone", "password1", "password2", "role", "resort")}),
    )

    def owner_statement(self, obj):
        if not obj or obj.role != User.Role.OWNER:
            return "-"

        from django.db.models import Sum
        from billing.models import Charge
        from collections_app.models import Payment

        owner_units = obj.owner_units.select_related("unit").all()
        if not owner_units:
            return "-"

        rows = []
        total_charged = 0
        total_paid = 0

        for ou in owner_units:
            unit = ou.unit
            charges_qs = Charge.objects.filter(unit=unit, status=Charge.Status.PUBLISHED)
            charged = charges_qs.aggregate(t=Sum("amount"))["t"] or 0
            paid = Payment.objects.filter(charge__unit=unit, charge__status=Charge.Status.PUBLISHED).aggregate(t=Sum("amount"))["t"] or 0
            balance = charged - paid
            total_charged += charged
            total_paid += paid

            statement_url = reverse("billing_statement")
            statement_url = f"{statement_url}?building_no={unit.building_no}&unit_no={unit.unit_no}"
            rows.append(
                format_html(
                    "<tr>"
                    "<td class='p-2'>{}</td>"
                    "<td class='p-2'>{}</td>"
                    "<td class='p-2'>{}</td>"
                    "<td class='p-2'>{}</td>"
                    "<td class='p-2'><a class='button' href='{}'>Statement</a></td>"
                    "</tr>",
                    unit.unit_key,
                    _format_currency(charged),
                    _format_currency(paid),
                    _format_currency(balance),
                    statement_url,
                )
            )

        grand_balance = total_charged - total_paid
        body = format_html_join("", "{}", ((r,) for r in rows))
        table = format_html(
            "<div style='overflow:auto'>"
            "<table style='min-width:700px' class='border'>"
            "<thead><tr>"
            "<th class='p-2 text-left'>Unit</th>"
            "<th class='p-2 text-left'>Total Charged</th>"
            "<th class='p-2 text-left'>Total Paid</th>"
            "<th class='p-2 text-left'>Balance</th>"
            "<th class='p-2 text-left'>Actions</th>"
            "</tr></thead>"
            "<tbody>{}</tbody>"
            "</table>"
            "</div>"
            "<div style='margin-top:8px'>"
            "<strong>Grand Total:</strong> {} | <strong>Paid:</strong> {} | <strong>Balance:</strong> {}"
            "</div>",
            body,
            _format_currency(total_charged),
            _format_currency(total_paid),
            _format_currency(grand_balance),
        )
        return table

    owner_statement.short_description = "Owner Statement"

    def total_debt_display(self, obj):
        if obj.role == User.Role.OWNER:
            return _format_currency(obj.total_debt)
        return "-"
    total_debt_display.short_description = "Total Debt"

    def total_paid_display(self, obj):
        if obj.role == User.Role.OWNER:
            return _format_currency(obj.total_paid)
        return "-"
    total_paid_display.short_description = "Total Paid"

    def remaining_balance_display(self, obj):
        if obj.role == User.Role.OWNER:
            balance = obj.remaining_balance
            try:
                color = "red" if balance > 0 else "green"
            except Exception:
                color = "red"
            return format_html('<span style="color: {}">{}</span>', color, _format_currency(balance))
        return "-"
    remaining_balance_display.short_description = "Remaining Balance"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only a superuser may place a user in any resort; anyone else with
        # access to this admin can only assign their own.
        if db_field.name == "resort" and not request.user.is_superuser:
            kwargs["queryset"] = Resort.objects.filter(pk=request.user.resort_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # A new user with no resort picked used to land in whichever resort
        # happened to be first (Delta Sharm), so staff for any other resort
        # couldn't be created here. Fall back to the creator's own resort.
        if not obj.resort:
            obj.resort = request.user.resort if not request.user.is_superuser and request.user.resort_id else Resort.objects.first()
        super().save_model(request, obj, form, change)


class TeamMemberInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    autocomplete_fields = ("user",)

    def _can_manage_members(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.role in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]

    def has_add_permission(self, request, obj=None):
        return self._can_manage_members(request)

    def has_change_permission(self, request, obj=None):
        return self._can_manage_members(request)

    def has_delete_permission(self, request, obj=None):
        return self._can_manage_members(request)


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("id", "name", "members_count", "created_by", "created_at")
    search_fields = ("name",)
    inlines = (TeamMemberInline,)

    def _is_manager(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", None) in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]

    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        # Allow staff to view teams for lookup/autocomplete and visibility.
        return bool(getattr(request.user, "is_staff", False)) and getattr(request.user, "role", None) != User.Role.OWNER

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_add_permission(self, request):
        return self._is_manager(request)

    def has_change_permission(self, request, obj=None):
        return self._is_manager(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_manager(request)

    def members_count(self, obj):
        return obj.memberships.count()

    def save_model(self, request, obj, form, change):
        if not obj.pk and request.user and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.action(description="Approve selected member requests")
def approve_member_requests(modeladmin, request, queryset):
    if not (request.user.is_superuser or request.user.role in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]):
        raise PermissionDenied("You are not allowed to approve member requests.")
    for req in queryset:
        req.approve(request.user)


@admin.action(description="Reject selected member requests")
def reject_member_requests(modeladmin, request, queryset):
    if not (request.user.is_superuser or request.user.role in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]):
        raise PermissionDenied("You are not allowed to reject member requests.")
    for req in queryset:
        req.reject(request.user)


@admin.register(TeamMembershipRequest)
class TeamMembershipRequestAdmin(RoleBasedAdminMixin, ModelAdmin):
    required_roles = [
        User.Role.DATA_ENTRY,
        User.Role.SUPERVISOR,
        User.Role.RECEPTION,
        User.Role.FINANCIAL_MANAGER,
        User.Role.GENERAL_MANAGER,
    ]
    list_display = (
        "id",
        "team",
        "user",
        "action",
        "status",
        "requested_by",
        "requested_at",
        "decided_by",
        "decided_at",
    )
    list_filter = ("status", "action", "team")
    search_fields = ("team__name", "user__phone")
    autocomplete_fields = ("team", "user")
    actions = [approve_member_requests, reject_member_requests]

    def _is_manager(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", None) in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]

    def has_change_permission(self, request, obj=None):
        if self._is_manager(request):
            return True
        # Non-managers can create requests but cannot modify them after creation.
        return False

    def has_delete_permission(self, request, obj=None):
        if self._is_manager(request):
            return True
        if obj is None:
            return False
        return (
            obj.requested_by_id == request.user.id
            and obj.status == TeamMembershipRequest.Status.PENDING
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if getattr(request.user, "role", None) in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]:
            return qs
        return qs.filter(requested_by=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.pk and request.user and request.user.is_authenticated:
            obj.requested_by = request.user
        super().save_model(request, obj, form, change)

        # Financial/GM can apply immediately without review.
        if not change and request.user and request.user.is_authenticated:
            if request.user.is_superuser or request.user.role in ["FINANCIAL_MANAGER", "GENERAL_MANAGER"]:
                if obj.status == TeamMembershipRequest.Status.PENDING:
                    obj.approve(request.user)

