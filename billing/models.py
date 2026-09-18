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

    @property
    def active_deferral(self):
        return self.deferrals.order_by("-created_at").first()


class PaymentDeferral(models.Model):
    """
    A record that a charge's due date was pushed back — append-only, since
    it doubles as the legal record of "payment deferred to <date>" the owner
    sees. Self-service (owner/tenant, <=3 days from today) creates an
    AUTO_APPROVED row instantly; anything longer is never created through
    the self-service endpoint at all — only staff can enter it directly
    (STAFF_APPROVED), since that requires the accountant's own judgment.
    """
    class Status(models.TextChoices):
        AUTO_APPROVED = "AUTO_APPROVED", "Auto-approved (self-service)"
        STAFF_APPROVED = "STAFF_APPROVED", "Approved by staff"

    charge = models.ForeignKey(Charge, on_delete=models.CASCADE, related_name="deferrals")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_deferrals")
    deferred_to = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices)

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_deferrals",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.charge} -> deferred to {self.deferred_to} ({self.status})"


class PaymentPlan(models.Model):
    """
    A request to pay a large charge in installments. Mirrors
    users.models.TeamMembershipRequest's PENDING/APPROVED/REJECTED shape and
    approve()/reject() pattern — the accountant (FINANCIAL_MANAGER/
    GENERAL_MANAGER today; a dedicated Role.ACCOUNTANT is a separate,
    not-yet-built gap) reviews the owner's proposed installments as a whole.
    """
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    charge = models.ForeignKey(Charge, on_delete=models.CASCADE, related_name="payment_plans")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_plans")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_payment_plans",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.charge} - plan by {self.requested_by.phone} ({self.status})"

    def approve(self, by_user):
        if self.status != self.Status.PENDING:
            return
        self.status = self.Status.APPROVED
        self.decided_by = by_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decided_by", "decided_at"])

    def reject(self, by_user, note=""):
        if self.status != self.Status.PENDING:
            return
        self.status = self.Status.REJECTED
        self.decided_by = by_user
        self.decided_at = timezone.now()
        if note:
            self.decision_note = str(note)
            self.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
        else:
            self.save(update_fields=["status", "decided_by", "decided_at"])


class PaymentPlanInstallment(models.Model):
    plan = models.ForeignKey(PaymentPlan, on_delete=models.CASCADE, related_name="installments")
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.plan_id} - {self.due_date} - {self.amount}"