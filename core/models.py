from django.db import models
from django.conf import settings


class Resort(models.Model):
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("owner", "unit")]

    def __str__(self):
        return f"{self.owner.phone} -> {self.unit.unit_key}"