from django.contrib import admin
from django.utils import timezone
from unfold.admin import ModelAdmin

from core.models import Resort
from core.permissions import RoleBasedAdminMixin
from users.models import User

from .models import Announcement


@admin.action(description="Publish selected announcements", permissions=["change"])
def publish_announcements(modeladmin, request, queryset):
    # Only rows that weren't live get a fresh published_at, so the feed order
    # reflects when a post actually went up.
    queryset.filter(is_published=False).update(is_published=True, published_at=timezone.now())


@admin.action(description="Unpublish selected announcements", permissions=["change"])
def unpublish_announcements(modeladmin, request, queryset):
    queryset.update(is_published=False, published_at=None)


@admin.register(Announcement)
class AnnouncementAdmin(RoleBasedAdminMixin, ModelAdmin):
    """
    Staff author the resort feed here. Non-superusers are locked to their own
    resort: they only see its announcements and can only post to it.
    """
    required_roles = [User.Role.RESORT_ADMIN, User.Role.GENERAL_MANAGER, User.Role.SUPERVISOR]

    list_display = ("title", "kind", "resort", "is_published", "published_at", "expires_at")
    list_filter = ("kind", "is_published", "resort")
    search_fields = ("title", "body")
    actions = [publish_announcements, unpublish_announcements]
    fieldsets = (
        (None, {"fields": ("resort", "kind", "title", "body", "image")}),
        ("Listing / event details", {"fields": ("price", "contact_phone", "event_date")}),
        ("Visibility", {"fields": ("is_published", "expires_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(resort=request.user.resort)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resort" and not request.user.is_superuser:
            kwargs["queryset"] = Resort.objects.filter(pk=request.user.resort_id)
            kwargs["initial"] = request.user.resort_id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        if not request.user.is_superuser:
            obj.resort_id = request.user.resort_id
        # Taking a post down resets published_at so re-publishing it later
        # puts it back at the top of the feed rather than its old slot.
        if change and "is_published" in form.changed_data and not obj.is_published:
            obj.published_at = None
        super().save_model(request, obj, form, change)
