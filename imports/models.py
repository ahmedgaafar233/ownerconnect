from django.db import models


class ImportSource(models.Model):
    """
    إعدادات الاستيراد الخاصة بكل Resort.
    mapping = JSON فيه خريطة الأعمدة/الإعدادات.
    """
    class SourceType(models.TextChoices):
        EXCEL_UPLOAD = "EXCEL_UPLOAD", "Excel Upload"

    class FormatType(models.TextChoices):
        LONG = "LONG", "Row per charge (long)"
        WIDE = "WIDE", "Row per unit (wide)"

    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="import_sources")

    source_type = models.CharField(max_length=30, choices=SourceType.choices, default=SourceType.EXCEL_UPLOAD)
    format_type = models.CharField(max_length=10, choices=FormatType.choices, default=FormatType.WIDE)

    # Simplified config for now, we will handle logic in the wizard
    mapping = models.JSONField(default=dict, help_text="Mapping configuration for columns")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.resort.name} - {self.get_format_type_display()}"


class ExcelUpload(models.Model):
    """
    ملف Excel/CSV مرفوع للاستيراد.
    """
    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="excel_uploads")
    source = models.ForeignKey(ImportSource, on_delete=models.PROTECT, related_name="uploads", null=True, blank=True)

    file = models.FileField(upload_to="excel_uploads/")
    original_name = models.CharField(max_length=255, blank=True, default="")

    uploaded_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="uploads"
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="UPLOADED")  # UPLOADED/PROCESSED/FAILED
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.resort.name} - {self.original_name or self.file.name}"