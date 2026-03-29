from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Charge(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        REVIEWED = "REVIEWED", "Reviewed by Staff"
        PUBLISHED = "PUBLISHED", "Published"
        REJECTED = "REJECTED", "Rejected"

    class Type(models.TextChoices):
        ELECTRICITY = "ELECTRICITY", "Electricity"
        WATER = "WATER", "Water"
        SERVICES = "SERVICES", "Services"
        ANNUAL_MAINTENANCE = "ANNUAL_MAINTENANCE", "Annual Maintenance"
        OTHER = "OTHER", "Other"

    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="charges")
    unit = models.ForeignKey("core.Unit", on_delete=models.CASCADE, related_name="charges")

    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Leave empty for annual charges."
    )

    type = models.CharField(max_length=30, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True, default="")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_charges",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    source_upload = models.ForeignKey(
        "imports.ExcelUpload",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_charges",
    )
    source_row = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["resort", "status"]),
            models.Index(fields=["unit", "status"]),
            models.Index(fields=["year", "month"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_upload", "source_row", "type"],
                name="uniq_charge_per_upload_row_type",
            )
        ]

    @property
    def total_paid(self):
        # مجموع التوزيعات اللي اتعملت على المديونية دي من الإيصالات
        return self.allocations.aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")

    @property
    def balance(self):
        return self.amount - self.total_paid

    @property
    def is_fully_paid(self):
        return self.balance <= 0

    def publish(self, by_user):
        self.status = Charge.Status.PUBLISHED
        self.approved_by = by_user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at"])

    def __str__(self):
        period = f"{self.year}-{self.month:02d}" if self.month else f"{self.year}"
        return f"{self.resort.name} {self.unit.unit_key} {self.type} {period} {self.amount}"