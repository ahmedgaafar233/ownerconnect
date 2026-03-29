from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from core.models import Resort
from core.permissions import DataEntryAdminMixin, ImportUploadMixin, ImportProcessMixin
from users.models import User

from .models import ExcelUpload
from .services import process_excel_upload


@admin.action(description="Process selected uploads (create PENDING charges)")
def process_selected_uploads(modeladmin, request, queryset):
    ok = 0
    fail = 0
    for upload in queryset:
        try:
            process_excel_upload(upload)
            ok += 1
        except Exception as e:
            fail += 1
            upload.status = "FAILED"
            upload.error = str(e)
            upload.save(update_fields=["status", "error"])
    if ok:
        messages.success(request, f"✓ Processed {ok} file(s) successfully.")
    if fail:
        messages.error(request, f"✗ {fail} file(s) failed to process.")


@admin.register(ExcelUpload)
class ExcelUploadAdmin(ImportUploadMixin, ModelAdmin):
    list_display = (
        "id", "resort", "original_name", "status_badge",
        "uploaded_by", "created_at", "processed_at",
    )
    list_filter = ("resort", "status", "created_at")
    search_fields = ("original_name",)
    actions = [process_selected_uploads]
    readonly_fields = (
        "status_badge", "file_info", "preview_data",
        "processing_result", "uploaded_by", "created_at",
    )

    fieldsets = (
        ("Upload", {
            "fields": ("resort", "file", "original_name"),
            "description": "Upload an Excel (.xlsx, .xls) or CSV (.csv) file.",
        }),
        ("Status", {
            "fields": ("status_badge", "uploaded_by", "created_at", "processed_at", "processing_result"),
        }),
        ("Data Preview", {
            "fields": ("file_info", "preview_data"),
            "classes": ("collapse",),
        }),
    )

    def get_exclude(self, request, obj=None):
        """Hide source field unless needed."""
        return ("source",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Auto-select first resort as default."""
        if db_field.name == "resort":
            first_resort = Resort.objects.first()
            if first_resort:
                kwargs["initial"] = first_resort.pk
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """Auto-set uploaded_by and original_name."""
        if not change:
            obj.uploaded_by = request.user
        if obj.file and not obj.original_name:
            obj.original_name = obj.file.name.split("/")[-1]
        super().save_model(request, obj, form, change)

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Only managers can process records
        if request.user.role not in [User.Role.FINANCIAL_MANAGER, User.Role.GENERAL_MANAGER]:
            if 'process_selected_uploads' in actions:
                del actions['process_selected_uploads']
        return actions

    def status_badge(self, obj):
        colors = {
            "UPLOADED": ("#f97316", "#fff7ed", "⏳"),
            "PROCESSED": ("#16a34a", "#f0fdf4", "✓"),
            "FAILED": ("#dc2626", "#fef2f2", "✗"),
            "PROCESSING": ("#2563eb", "#eff6ff", "⟳"),
        }
        color, bg, icon = colors.get(obj.status, ("#6b7280", "#f9fafb", "?"))
        label = obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        return format_html(
            '<span style="background:{bg};color:{c};padding:4px 12px;border-radius:12px;'
            'font-weight:600;font-size:0.85rem;">{icon} {label}</span>',
            bg=bg, c=color, icon=icon, label=label,
        )
    status_badge.short_description = "Status"

    def file_info(self, obj):
        if obj.file:
            try:
                size = obj.file.size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{size / 1024:.1f} KB"
                ext = obj.file.name.rsplit(".", 1)[-1].upper() if "." in obj.file.name else "?"
                return format_html(
                    '<div style="display:flex;gap:16px;align-items:center;">'
                    '<span style="font-size:1.5rem;">📄</span>'
                    '<div>'
                    '<strong>{name}</strong><br>'
                    '<span style="color:#6b7280;">{ext} • {size} • Uploaded {date}</span>'
                    '</div></div>',
                    name=obj.original_name or obj.file.name.split("/")[-1],
                    ext=ext,
                    size=size_str,
                    date=obj.created_at.strftime("%Y-%m-%d %H:%M") if obj.created_at else "—",
                )
            except Exception:
                return "File information unavailable"
        return "No file uploaded"
    file_info.short_description = "File Information"

    def preview_data(self, obj):
        """Show preview of first 10 rows."""
        if not obj.file:
            return "No file to preview"

        try:
            import pandas as pd
            fname = obj.file.path.lower()
            if fname.endswith(".csv"):
                df = pd.read_csv(obj.file.path, nrows=10)
            else:
                df = pd.read_excel(obj.file.path, nrows=10)

            html = '<div style="overflow-x:auto;max-height:400px;border:1px solid #e5e7eb;border-radius:8px;">'
            table = df.to_html(
                classes="table",
                index=False,
                border=0,
            )
            # Add basic styling
            table = table.replace(
                '<table',
                '<table style="width:100%;border-collapse:collapse;font-size:0.875rem;"'
            )
            table = table.replace(
                '<th',
                '<th style="background:#f3f4f6;padding:8px 12px;text-align:left;'
                'border-bottom:2px solid #e5e7eb;font-weight:600;white-space:nowrap;"'
            )
            table = table.replace(
                '<td',
                '<td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;white-space:nowrap;"'
            )
            html += table + '</div>'
            html += f'<p style="color:#6b7280;margin-top:8px;font-size:0.8rem;">Showing first 10 of {len(pd.read_excel(obj.file.path) if not fname.endswith(".csv") else pd.read_csv(obj.file.path))} rows</p>'

            return mark_safe(html)
        except Exception as e:
            return f"Preview not available: {str(e)}"
    preview_data.short_description = "Data Preview"

    def processing_result(self, obj):
        if obj.status == "PROCESSED":
            return format_html(
                '<span style="color:#16a34a;font-weight:600;">✓ {}</span>',
                obj.error or "Successfully processed"
            )
        elif obj.status == "FAILED":
            return format_html(
                '<div style="color:#dc2626;">'
                '<strong>✗ Processing Failed</strong><br>'
                '<pre style="background:#fef2f2;padding:8px;border-radius:4px;'
                'font-size:0.8rem;max-height:200px;overflow-y:auto;white-space:pre-wrap;">{}</pre>'
                '</div>',
                obj.error or "Unknown error"
            )
        return format_html(
            '<span style="color:#6b7280;">Not processed yet — select and use '
            '"Process selected uploads" action</span>'
        )
    processing_result.short_description = "Processing Result"

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status in ["PROCESSED", "FAILED"]:
            return self.readonly_fields + ("resort", "file", "original_name")
        return self.readonly_fields