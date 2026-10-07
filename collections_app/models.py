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

    # The resort this payment is for — always set. A session spanning
    # multiple units (combined payment) leaves `unit` null; a single-unit
    # session still populates it as before.
    resort = models.ForeignKey(
        "core.Resort",
        on_delete=models.CASCADE,
        related_name="payment_sessions",
    )
    unit = models.ForeignKey(
        "core.Unit",
        on_delete=models.CASCADE,
        related_name="payment_sessions",
        null=True,
        blank=True,
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

    # Set only when `amount` is less than the full due across the selected
    # charges — the date the owner committed to pay the rest by. The
    # webhook auto-creates a PaymentDeferral to this date for whatever
    # charges this payment didn't fully cover.
    remaining_due_date = models.DateField(null=True, blank=True)

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
    # Who handed the money over — the owner or the tenant of the unit. The name
    # and role are copied here at payment time (like the receipt itself): a
    # receipt must keep saying who paid even if that person is renamed or
    # their account is later removed. Blank on payments recorded before this
    # existed (the receipt then falls back to the unit's owner, as it used to).
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments_made",
    )
    payer_name = models.CharField(max_length=255, blank=True, default="")
    payer_role = models.CharField(max_length=20, blank=True, default="")
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

class PaymentMethod(models.Model):
    """
    A way an owner or tenant prefers to pay: a mobile wallet, an InstaPay
    address, or Fawry. It is a saved preference plus the little the method
    needs — a wallet's phone number, an InstaPay address — never a card
    number: card details are only ever typed into the payment gateway's own
    secure form and never touch this server (cards are added through the
    gateway once online payments go live, and only a token would be stored).
    """
    class Kind(models.TextChoices):
        CARD = "CARD", "Bank card"
        WALLET = "WALLET", "Mobile wallet"
        INSTAPAY = "INSTAPAY", "InstaPay"
        FAWRY = "FAWRY", "Fawry"

    class Wallet(models.TextChoices):
        VODAFONE_CASH = "VODAFONE_CASH", "Vodafone Cash"
        ORANGE_CASH = "ORANGE_CASH", "Orange Cash"
        ETISALAT_CASH = "ETISALAT_CASH", "Etisalat Cash"
        WE_PAY = "WE_PAY", "WE Pay"
        OTHER = "OTHER", "Other wallet"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_methods")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # What the app shows for it, e.g. "Vodafone Cash · +20 100 000 0000".
    label = models.CharField(max_length=120)

    wallet_provider = models.CharField(max_length=15, choices=Wallet.choices, blank=True, default="")
    wallet_phone = models.CharField(max_length=20, blank=True, default="")
    instapay_address = models.CharField(max_length=80, blank=True, default="")

    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.user.phone}: {self.label}"
