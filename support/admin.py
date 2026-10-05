from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.urls import reverse
from unfold.admin import ModelAdmin, StackedInline
from core.models import Resort
from core.permissions import ReceptionAdminMixin, RoleBasedAdminMixin, SupervisorAdminMixin
from users.models import User
from core.models import Notification
from core.notifications import notify_user
from .models import Message, PassScan, Ticket, VisitorPass
from .passes import PassNotPending, approve_pass, notify_pass_decision
from .routing import DESK_ROLES, limit_to_desk


class MessageInline(StackedInline):
    model = Message
    extra = 1
    readonly_fields = ("created_at", "message_type", "attachment_display")
    fields = ("sender", "message_type", "content", "attachment", "attachment_display", "created_at")
    ordering = ("created_at",)
    
    def attachment_display(self, obj):
        if obj.attachment:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.attachment.url,
                obj.attachment_name or "View Attachment"
            )
        return "No attachment"
    attachment_display.short_description = "Attachment"


@admin.register(Ticket)
class TicketAdmin(ReceptionAdminMixin, ModelAdmin):
    """
    The service desk. Requests from owners land here; the Maintenance and
    Housekeeping desks each see their own department's queue, assign a
    technician and move the request along — the owner is told at each step.
    """
    required_roles = ReceptionAdminMixin.required_roles + list(DESK_ROLES)

    list_display = ("mobile_ticket_id", "category", "service_type", "priority_display", "subject", "owner", "unit_info", "status_display", "technician_display", "created_at")
    list_filter = ("category", "service_type", "status", "priority", "created_at")
    search_fields = ("subject", "owner__phone", "mobile_ticket_id", "unit__unit_key")
    inlines = [MessageInline]
    autocomplete_fields = ["unit", "owner"]
    
    fieldsets = (
        ("Ticket Information", {
            "fields": ("owner", "unit", "category", "service_type", "priority", "subject", "description")
        }),
        ("Status & Assignment", {
            "fields": ("status", "assigned_to", "technician_name", "mobile_ticket_id")
        }),
        ("Resolution", {
            "fields": ("resolution_notes", "resolved_by", "resolved_at"),
            "classes": ("collapse",)
        }),
    )
    
    readonly_fields = ("mobile_ticket_id", "resolved_by", "resolved_at")

    # What the owner asked for is theirs to state; the desk only works it.
    _request_fields = ("owner", "unit", "category", "service_type", "subject", "description")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and not request.user.is_superuser:
            return tuple(fields) + self._request_fields
        return fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            staff = User.objects.exclude(role__in=[User.Role.OWNER, User.Role.TENANT])
            if not request.user.is_superuser:
                staff = staff.filter(resort_id=request.user.resort_id)
            kwargs["queryset"] = staff
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        # A request is a record; close it rather than delete it.
        return request.user.is_superuser

    @admin.display(description="Technician")
    def technician_display(self, obj):
        if obj.technician_name:
            return obj.technician_name
        if obj.assigned_to:
            return obj.assigned_to.fullname or obj.assigned_to.phone
        return "Unassigned"

    def priority_display(self, obj):
        colors = {
            "LOW": "green",
            "MEDIUM": "orange", 
            "HIGH": "red",
            "URGENT": "darkred"
        }
        color = colors.get(obj.priority, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_display.short_description = "Priority"

    def status_display(self, obj):
        colors = {
            "OPEN": "red",
            "ASSIGNED": "orange",
            "IN_PROGRESS": "blue",
            "PENDING_OWNER": "purple",
            "COMPLETED": "green",
            "CLOSED": "gray"
        }
        color = colors.get(obj.status, "gray")
        overdue_indicator = " ⚠️" if obj.is_overdue else ""
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{}</span>',
            color,
            obj.get_status_display(),
            overdue_indicator
        )
    status_display.short_description = "Status"

    def unit_info(self, obj):
        return f"{obj.unit.building_no} / {obj.unit.unit_no}"
    unit_info.short_description = "Unit"

    def assigned_to_display(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.phone
        return "Unassigned"
    assigned_to_display.short_description = "Assigned To"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user and request.user.role == 'OWNER':
            # Owners can only see their own tickets
            return qs.filter(owner=request.user)
        qs = qs.select_related('owner', 'unit', 'assigned_to')
        # Row-level fix: ReceptionAdminMixin only gates which roles may open
        # this admin at all — any RECEPTION/SUPERVISOR user could previously
        # browse and reply to every resort's tickets, not just their own.
        if request.user.is_superuser:
            return qs
        return limit_to_desk(request.user, qs.filter(resort=request.user.resort))

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            # A staff-created ticket belongs to its unit's resort — it used to
            # be filed under whichever resort happened to be first.
            obj.resort = obj.unit.resort

        old_status = form.initial.get("status") if change and form is not None else None
        # Sending someone to the job is what "assigned" means.
        if obj.status == obj.Status.OPEN and (obj.assigned_to_id or obj.technician_name):
            obj.status = obj.Status.ASSIGNED
        
        # Auto-assign resolution info when completing
        if obj.status == obj.Status.COMPLETED and not obj.resolved_by:
            obj.resolved_by = request.user
        
        super().save_model(request, obj, form, change)

        if old_status is not None and obj.status != old_status:
            try:
                notify_user(
                    obj.owner,
                    title="Service Request Update",
                    body=f"{obj.subject}: {obj.get_status_display()}",
                    notif_type=Notification.Type.TICKET_STATUS,
                    data={"type": "ticket_status", "ticket_id": obj.id, "status": obj.status},
                )
            except Exception:
                pass


@admin.register(PassScan)
class PassScanAdmin(RoleBasedAdminMixin, ModelAdmin):
    """
    Read-only audit log of gate and beach/pool scans. Nobody edits or deletes
    it here — it exists so management can see who got in, who was refused
    and why, and how many towels went out.
    """
    required_roles = [User.Role.RESORT_ADMIN, User.Role.GENERAL_MANAGER, User.Role.SUPERVISOR]

    list_display = ("scanned_at", "resort", "point", "result", "deny_reason", "pass_code", "visitor_name", "towels_issued", "scanned_by")
    list_filter = ("point", "result", "deny_reason", "scanned_at", "resort")
    search_fields = ("pass_code", "visitor_pass__visitor_name", "scanned_by__phone")
    date_hierarchy = "scanned_at"

    @admin.display(description="Visitor")
    def visitor_name(self, obj):
        return obj.visitor_pass.visitor_name if obj.visitor_pass_id else "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("visitor_pass", "scanned_by", "resort")
        if request.user.is_superuser:
            return qs
        return qs.filter(resort=request.user.resort)


class VisitorPassAdminForm(forms.ModelForm):
    class Meta:
        model = VisitorPass
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get("unit")
        valid_from, valid_to = cleaned.get("valid_from"), cleaned.get("valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            raise ValidationError("The pass must end after it starts.")
        if unit and not self.instance.pk:
            # The pass appears in the app under a real account: the unit's
            # owner if it has one, otherwise whoever else is linked to it.
            resident = (
                User.objects.filter(owner_units__unit=unit, role=User.Role.OWNER).first()
                or User.objects.filter(owner_units__unit=unit).first()
            )
            if resident is None:
                raise ValidationError(
                    "This unit has no owner or tenant linked yet, so there is no account for the pass to appear under."
                )
            self.instance.owner = resident
        return cleaned


@admin.action(description="Cancel selected passes", permissions=["change"])
def cancel_passes(modeladmin, request, queryset):
    queryset.filter(
        status__in=(VisitorPass.Status.ACTIVE, VisitorPass.Status.PENDING)
    ).update(status=VisitorPass.Status.CANCELLED)


@admin.action(description="Approve selected pass requests", permissions=["change"])
def approve_pass_requests(modeladmin, request, queryset):
    for visitor_pass in queryset.filter(status=VisitorPass.Status.PENDING):
        try:
            approve_pass(visitor_pass, request.user)
        except PassNotPending:
            pass  # someone else decided it a moment ago


@admin.register(VisitorPass)
class VisitorPassAdmin(RoleBasedAdminMixin, ModelAdmin):
    """
    Where the resort itself issues, finds and cancels gate / beach-pool passes
    (a resident can also raise their own from the app). Staff pick the unit;
    the pass lands in that unit's owner's app. Issuing here is not limited by
    the unit's card allowance — that cap binds residents, not the resort.
    """
    required_roles = [
        User.Role.RECEPTION, User.Role.SUPERVISOR, User.Role.RESORT_ADMIN, User.Role.GENERAL_MANAGER,
    ]
    form = VisitorPassAdminForm

    list_display = ("pass_code", "pass_type", "visitor_name", "unit", "owner", "valid_from", "valid_to", "status", "issued_by")
    list_filter = ("pass_type", "status", "resort")
    search_fields = ("pass_code", "visitor_name", "unit__unit_key", "owner__phone")
    autocomplete_fields = ("unit",)
    actions = [approve_pass_requests, cancel_passes]

    _issue_fields = ("unit", "pass_type", "visitor_name", "national_id_or_passport", "car_plate", "valid_from", "valid_to")

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {"fields": self._issue_fields}),)
        return (
            (None, {"fields": ("qr_code", "pass_code") + self._issue_fields + ("status", "rejection_reason")}),
            ("Issued", {"fields": ("owner", "issued_by", "decided_by", "decided_at", "created_at")}),
        )

    def get_readonly_fields(self, request, obj=None):
        # Once issued, the unit and the resident can't be swapped — change
        # the dates/status or cancel and issue a new pass.
        if obj is None:
            return ()
        return ("qr_code", "pass_code", "unit", "owner", "issued_by", "decided_by", "decided_at", "created_at")

    @admin.display(description="QR code")
    def qr_code(self, obj):
        if not obj or not obj.pk:
            return "-"
        if obj.status != VisitorPass.Status.ACTIVE:
            # A pending/rejected/cancelled pass must not look usable.
            return f"No QR — this pass is {obj.get_status_display().lower()}."
        import segno

        # The QR encodes the bare pass code — exactly what the app shows —
        # so a phone camera and a handheld scanner both read it the same way.
        svg = segno.make(obj.pass_code, error="m").svg_inline(scale=6, dark="#000", light="#fff", border=2)
        return mark_safe(f'<div style="display:inline-block;background:#fff;padding:8px">{svg}</div>')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Validation, not just the autocomplete list, must be resort-locked.
        if db_field.name == "unit" and not request.user.is_superuser:
            from core.models import Unit
            kwargs["queryset"] = Unit.objects.filter(resort_id=request.user.resort_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("unit", "owner", "issued_by", "resort")
        if request.user.is_superuser:
            return qs
        return qs.filter(resort=request.user.resort)

    def has_delete_permission(self, request, obj=None):
        # Cancel instead — the scan log refers back to passes.
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        decided = (
            change
            and "status" in form.changed_data
            and form.initial.get("status") == VisitorPass.Status.PENDING
            and obj.status in (VisitorPass.Status.ACTIVE, VisitorPass.Status.REJECTED)
        )
        if not change:
            obj.resort = obj.unit.resort
            obj.issued_by = request.user
        if decided:
            obj.decided_by = request.user
            obj.decided_at = timezone.now()
        super().save_model(request, obj, form, change)
        if decided:
            try:
                notify_pass_decision(obj)
            except Exception:
                pass
