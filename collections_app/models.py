import json
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone


class PaymentSession(models.Model):
    """
    Immutable record created BEFORE redirecting an owner to the Paymob checkout page.
    The webhook MUST use this session to determine the correct amount and charge_ids —
    it must NEVER trust values sent in the Paymob callback body.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Payment"
        COMPLETED = "COMPLETED", "Completed"
        EXPIRED = "EXPIRED", "Expired"
        FAILED = "FAILED", "Failed"

    # Paymob order identifier returned to the webhook
    merchant_order_id = models.CharField(max_length=64, unique=True, db_index=True)

    # The authenticated owner who initiated the payment
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_sessions",
    )

    # The resort and unit this payment is for
    resort = models.ForeignKey(
        "core.Resort",
        on_delete=models.CASCADE,
        related_name="payment_sessions",
    )
    unit = models.ForeignKey(
        "core.Unit",
        on_delete=models.CASCADE,
        related_name="payment_sessions",
    )

    # Exact amount computed server-side at session creation — webhook must use THIS
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    # JSON-serialised list of Charge PKs validated at session creation — webhook uses THESE
    _charge_ids_json = models.TextField(
        db_column="charge_ids_json",
        help_text="JSON array of billing.Charge PKs committed to this session.",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    # Sessions expire after 30 minutes — checked before processing the webhook
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Payment Session"
        verbose_name_plural = "Payment Sessions"
        indexes = [
            models.Index(fields=["merchant_order_id"]),
            models.Index(fields=["owner", "status"]),
        ]

    # ── charge_ids helpers ───────────────────────────────────────────────────────

    @property
    def charge_ids(self) -> list[int]:
        """Return the stored charge ID list as a Python list of ints."""
        return json.loads(self._charge_ids_json)

    @charge_ids.setter
    def charge_ids(self, value: list[int]) -> None:
        self._charge_ids_json = json.dumps([int(v) for v in value])

    # ── state helpers ────────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def mark_completed(self) -> None:
        self.status = self.Status.COMPLETED
        self.save(update_fields=["status"])

    def mark_failed(self) -> None:
        self.status = self.Status.FAILED
        self.save(update_fields=["status"])

    def __str__(self) -> str:
        return f"PaymentSession [{self.merchant_order_id}] {self.amount} EGP — {self.status}"


# ──────────────────────────────────────────────────────────────────────────────


class Payment(models.Model):
    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="payments")
    unit = models.ForeignKey("core.Unit", on_delete=models.CASCADE, related_name="payments")

    receipt_no = models.CharField(max_length=100)  # رقم الإيصال الورقي
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    # Generated once at payment time and never regenerated — the legal
    # record of what was paid, so it must stay frozen even if the
    # underlying charges get edited later. Best-effort: null if generation
    # failed (see collections_app/receipts.py).
    receipt_pdf = models.FileField(upload_to="receipts/%Y/%m/", null=True, blank=True)

    paid_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_payments",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["unit", "paid_at"]),
            models.Index(fields=["resort", "paid_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.unit.unit_key} - {self.receipt_no} - {self.total_amount}"

    @property
    def unit_balance(self) -> Decimal:
        """Calculate the remaining debt for this unit as of now."""
        from billing.models import Charge
        from django.db.models import Sum

        charges = Charge.objects.filter(unit=self.unit, status=Charge.Status.PUBLISHED)
        total_debt = charges.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_paid = charges.aggregate(total=Sum("allocations__amount"))["total"] or Decimal("0.00")
        return total_debt - total_paid

    @property
    def unit_is_paid_off(self) -> bool:
        return self.unit_balance <= Decimal("0.00")


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    charge = models.ForeignKey("billing.Charge", on_delete=models.CASCADE, related_name="allocations")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.payment.receipt_no} -> charge#{self.charge_id} {self.amount}"