from django.db import models
from django.conf import settings


class Resort(models.Model):
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    logo = models.ImageField(upload_to="resort_logos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Unit(models.Model):
    resort = models.ForeignKey(Resort, on_delete=models.CASCADE, related_name="units")
    unit_key = models.CharField(max_length=100)  # مثال: 12/305
    building_no = models.CharField(max_length=50, blank=True, default="")
    unit_no = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("resort", "unit_key")]

    def __str__(self):
        if self.building_no or self.unit_no:
            return f"{self.resort.name} - {self.building_no}/{self.unit_no} ({self.unit_key})"
        return f"{self.resort.name} - {self.unit_key}"


class OwnerUnit(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owner_units"
    )
    unit = models.ForeignKey(
        "core.Unit",
        on_delete=models.CASCADE,
        related_name="owner_units"
    )
    # Only meaningful for a Tenant row today: a Tenant must never see/act on
    # charges dated before their own move-in. Left null for existing/Owner
    # rows so nothing is retroactively restricted until staff back-fill it.
    lease_start_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("owner", "unit")]

    def __str__(self):
        return f"{self.owner.phone} -> {self.unit.unit_key}"


class Notification(models.Model):
    class Type(models.TextChoices):
        PAYMENT_SUCCESS = "PAYMENT_SUCCESS", "Payment Successful"
        PAYMENT_DEFERRED = "PAYMENT_DEFERRED", "Payment Deferred"
        PAYMENT_PLAN_DECIDED = "PAYMENT_PLAN_DECIDED", "Payment Plan Decided"
        TICKET_REPLY = "TICKET_REPLY", "Support Reply"
        UNIT_ACTIVITY = "UNIT_ACTIVITY", "Unit Activity"
        OTHER = "OTHER", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    resort = models.ForeignKey(
        Resort,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.OTHER)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    data = models.JSONField(blank=True, default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.user.phone} - {self.title}"