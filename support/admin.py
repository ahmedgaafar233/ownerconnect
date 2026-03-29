from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from unfold.admin import ModelAdmin, StackedInline
from core.permissions import ReceptionAdminMixin, SupervisorAdminMixin
from .models import Ticket, Message


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
    list_display = ("mobile_ticket_id", "category", "priority_display", "subject", "owner", "unit_info", "status_display", "assigned_to_display", "created_at")
    list_filter = ("category", "status", "priority", "created_at")
    search_fields = ("subject", "owner__phone", "mobile_ticket_id", "unit__unit_key")
    inlines = [MessageInline]
    autocomplete_fields = ["unit", "owner", "assigned_to"]
    
    fieldsets = (
        ("Ticket Information", {
            "fields": ("owner", "unit", "category", "priority", "subject", "description")
        }),
        ("Status & Assignment", {
            "fields": ("status", "assigned_to", "mobile_ticket_id")
        }),
        ("Resolution", {
            "fields": ("resolution_notes", "resolved_by", "resolved_at"),
            "classes": ("collapse",)
        }),
    )
    
    readonly_fields = ("mobile_ticket_id", "resolved_by", "resolved_at")

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
        return qs.select_related('owner', 'unit', 'assigned_to')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            from core.models import Resort
            obj.resort = Resort.objects.first()
        
        # Auto-assign resolution info when completing
        if obj.status == obj.Status.COMPLETED and not obj.resolved_by:
            obj.resolved_by = request.user
        
        super().save_model(request, obj, form, change)



