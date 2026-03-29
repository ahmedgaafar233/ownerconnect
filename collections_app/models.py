from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone


class Payment(models.Model):
    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="payments")
    unit = models.ForeignKey("core.Unit", on_delete=models.CASCADE, related_name="payments")

    receipt_no = models.CharField(max_length=100)  # رقم الإيصال الورقي
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

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

    def __str__(self):
        return f"{self.unit.unit_key} - {self.receipt_no} - {self.total_amount}"

    @property
    def unit_balance(self):
        """Calculate the remaining debt for this unit as of now"""
        from billing.models import Charge
        from django.db.models import Sum
        charges = Charge.objects.filter(unit=self.unit, status=Charge.Status.PUBLISHED)
        total_debt = charges.aggregate(total=Sum('amount'))['total'] or 0
        total_paid = charges.aggregate(total=Sum('allocations__amount'))['total'] or 0
        return total_debt - total_paid

    @property
    def unit_is_paid_off(self):
        """Check if the unit has fully paid all debts"""
        return self.unit_balance <= 0


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    charge = models.ForeignKey("billing.Charge", on_delete=models.CASCADE, related_name="allocations")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payment.receipt_no} -> charge#{self.charge_id} {self.amount}"