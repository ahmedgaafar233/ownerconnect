from django.contrib import admin
from django.db.models import Sum, Q, F
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from .models import Lease, LeaseAdult, LeaseDocument, MeterReading, Resort, Unit, UnitType, OwnerUnit, Notification
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
    list_display = ("id", "name", "is_active", "logo", "created_at")
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
    list_display = ("id", "resort", "unit_key", "building_no", "unit_no", "unit_type", "is_active")
    list_filter = ("resort", "unit_type", "is_active", HasBalanceFilter)
    search_fields = ("unit_key", "building_no", "unit_no")
    ordering = ("building_no", "unit_no")

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # A non-superuser GM may only pick unit types from their own resort.
        if db_field.name == "unit_type" and not request.user.is_superuser:
            kwargs["queryset"] = UnitType.objects.filter(resort=request.user.resort)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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


@admin.register(UnitType)
class UnitTypeAdmin(admin.ModelAdmin):
    """
    The per-resort table of unit sizes and their beach/pool card allowance
    (e.g. Studio = 2, 1 Bedroom + Living = 3). GM+ manage their own resort's
    rows; the mobile app can never raise an allowance, only staff can.
    """
    list_display = ("id", "resort", "name", "card_allowance")
    list_filter = ("resort",)
    search_fields = ("name",)

    def _is_manager(self, request):
        return request.user.is_superuser or getattr(request.user, "role", "") == "GENERAL_MANAGER"

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_add_permission(self, request):
        return self._is_manager(request)

    def has_change_permission(self, request, obj=None):
        return self._is_manager(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resort" and not request.user.is_superuser:
            kwargs["queryset"] = Resort.objects.filter(pk=request.user.resort_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(resort=request.user.resort)


@admin.register(OwnerUnit)
class OwnerUnitAdmin(GeneralManagerAdminMixin, admin.ModelAdmin):
    """GM+ can view; only superuser can add/change/delete."""
    list_display = ("id", "owner", "unit", "lease_start_date", "lease_end_date", "total_debt", "total_paid", "remaining_balance", "created_at")
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


@admin.register(Notification)
class NotificationAdmin(GeneralManagerAdminMixin, admin.ModelAdmin):
    """Read-only audit log of what was sent — GM/FM can view for debugging; only superuser can delete stale rows."""
    list_display = ("id", "user", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("user__phone", "title", "body")

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["GENERAL_MANAGER", "FINANCIAL_MANAGER"]

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return getattr(request.user, "role", "") in ["GENERAL_MANAGER", "FINANCIAL_MANAGER"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(resort=request.user.resort)

class _ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class LeaseAdultInline(_ReadOnlyInline):
    model = LeaseAdult
    fields = ("full_name", "relation", "national_id", "id_photo_link", "qr_code")
    readonly_fields = fields

    @admin.display(description="ID photo")
    def id_photo_link(self, obj):
        if not obj.pk or not obj.id_photo:
            return "—"
        return format_html('<a href="{}" target="_blank">View</a>', reverse("lease_adult_id_photo", args=[obj.pk]))

    @admin.display(description="QR code")
    def qr_code(self, obj):
        return obj.access_pass.pass_code if obj.access_pass_id else "—"


class LeaseDocumentInline(_ReadOnlyInline):
    model = LeaseDocument
    fields = ("kind", "label", "file_link")
    readonly_fields = fields

    @admin.display(description="File")
    def file_link(self, obj):
        if not obj.pk or not obj.file:
            return "—"
        return format_html('<a href="{}" target="_blank">View</a>', reverse("lease_document_file", args=[obj.pk]))


class LeaseMeterInline(_ReadOnlyInline):
    model = MeterReading
    fields = ("meter", "kind", "reading", "read_on", "recorded_by")
    readonly_fields = fields


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    """
    Who is renting each unit. Owners register these themselves from the app —
    the village doesn't approve them, it just reads them (Reception, Security
    and the managers need to know who is living where). So this is view-only;
    nothing here creates or edits a rental.
    """
    list_display = ("unit", "tenant_name", "tenant_phone", "term", "start_date", "end_date", "state", "occupants", "landlord")
    list_filter = ("term",)
    search_fields = ("unit__unit_key", "tenant_name", "tenant_phone", "landlord__phone")
    actions = ["end_selected_rentals"]
    inlines = (LeaseAdultInline, LeaseDocumentInline, LeaseMeterInline)
    readonly_fields = (
        "resort", "unit", "landlord", "tenant", "term", "start_date", "end_date", "tenant_name", "tenant_phone",
        "tenant_national_id", "id_photo_link", "occupants", "cancelled_at", "created_at",
    )
    fields = readonly_fields
    _ROLES = ("RESORT_ADMIN", "GENERAL_MANAGER", "SUPERVISOR", "RECEPTION")

    @admin.display(description="Status")
    def state(self, obj):
        return obj.status_on(timezone.localdate())

    @admin.display(description="ID photo")
    def id_photo_link(self, obj):
        if not obj.pk or not obj.tenant_id_photo:
            return "—"
        return format_html('<a href="{}" target="_blank">View ID photo</a>', reverse("lease_id_photo", args=[obj.pk]))

    @admin.action(description="End the selected rentals (cancel ones that haven't started)")
    def end_selected_rentals(self, request, queryset):
        """
        The safety valve for a rental an owner registered by mistake — or for
        someone who isn't actually the tenant. Ends it exactly as the owner's
        own "End rental" does, and tells the tenant.
        """
        from .leases import LeaseError, end_lease

        ended, skipped = 0, 0
        for lease in queryset.select_related("unit", "tenant", "resort"):
            try:
                end_lease(lease)
                ended += 1
            except LeaseError:
                skipped += 1  # already over
        self.message_user(request, f"{ended} rental(s) ended" + (f", {skipped} already over." if skipped else "."))

    def _can_see(self, request):
        return request.user.is_superuser or getattr(request.user, "role", "") in self._ROLES

    def has_module_permission(self, request):
        return self._can_see(request)

    def has_view_permission(self, request, obj=None):
        return self._can_see(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("unit", "landlord")
        if request.user.is_superuser:
            return qs
        return qs.filter(resort=request.user.resort)


@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    """
    Meter readings, taken by the village's Maintenance team (they read every
    meter). At a tenant's entry and exit they mark where one person's
    consumption ends and the next begins; each reading links itself to the
    rental its date falls in.
    """
    list_display = ("unit", "meter", "kind", "reading", "read_on", "lease", "recorded_by")
    list_filter = ("meter", "kind")
    search_fields = ("unit__unit_key", "note")
    autocomplete_fields = ("unit",)
    fields = ("unit", "meter", "kind", "reading", "read_on", "note", "lease", "recorded_by")
    readonly_fields = ("lease", "recorded_by")
    date_hierarchy = "read_on"
    _WRITERS = ("MAINTENANCE", "RESORT_ADMIN", "GENERAL_MANAGER", "SUPERVISOR")
    _READERS = _WRITERS + ("RECEPTION",)

    def _role(self, request):
        return getattr(request.user, "role", "")

    def has_module_permission(self, request):
        return request.user.is_superuser or self._role(request) in self._READERS

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or self._role(request) in self._READERS

    def has_add_permission(self, request):
        return request.user.is_superuser or self._role(request) in self._WRITERS

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or self._role(request) in self._WRITERS

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("unit", "lease", "recorded_by")
        return qs if request.user.is_superuser else qs.filter(resort=request.user.resort)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "unit" and not request.user.is_superuser:
            kwargs["queryset"] = Unit.objects.filter(resort=request.user.resort)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        obj.resort_id = obj.unit.resort_id
        super().save_model(request, obj, form, change)
