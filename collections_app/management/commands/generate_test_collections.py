"""
Management command to generate dummy payment data for testing the Daily Collections page.
Creates units, charges (~100,000 EGP total), and 50-100 payments across the last 3 days.
"""
import random
from decimal import Decimal
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Resort, Unit
from billing.models import Charge
from collections_app.models import Payment, PaymentAllocation


# Building/unit data for realistic dummy entries
BUILDINGS = [
    {"building": "10", "units": ["101", "102", "103", "104", "105", "106", "107", "108"]},
    {"building": "11", "units": ["201", "202", "203", "204", "205", "206"]},
    {"building": "12", "units": ["301", "302", "303", "304", "305"]},
    {"building": "15", "units": ["401", "402", "403", "404", "405", "406", "407"]},
    {"building": "20", "units": ["501", "502", "503", "504"]},
]

CHARGE_TYPES = [
    Charge.Type.ELECTRICITY,
    Charge.Type.WATER,
    Charge.Type.SERVICES,
    Charge.Type.ANNUAL_MAINTENANCE,
]


class Command(BaseCommand):
    help = "Generate dummy collections data for testing (units, charges, payments over 3 days)"

    def handle(self, *args, **options):
        resort = Resort.objects.first()
        if not resort:
            self.stderr.write("No resort found! Create a resort first.")
            return

        self.stdout.write(f"Using resort: {resort.name}")

        # ── Step 1: Create Units ─────────────────────────────────────────
        units = list(Unit.objects.filter(resort=resort))
        created_units = 0
        for bld in BUILDINGS:
            for u_no in bld["units"]:
                key = f"{bld['building']}/{u_no}"
                unit, created = Unit.objects.get_or_create(
                    resort=resort,
                    unit_key=key,
                    defaults={"building_no": bld["building"], "unit_no": u_no},
                )
                if created:
                    created_units += 1
                units.append(unit)

        self.stdout.write(self.style.SUCCESS(f"Units ready: {len(units)} total ({created_units} new)"))

        # ── Step 2: Create Charges totaling ~100,000 EGP ─────────────────
        target_debt = Decimal("100000.00")
        total_charged = Decimal("0.00")
        charges_created = 0

        # Distribute charges across units with random types
        random.shuffle(units)
        charge_objects = []

        while total_charged < target_debt:
            unit = random.choice(units)
            charge_type = random.choice(CHARGE_TYPES)
            amount = Decimal(str(random.randint(800, 5000)))

            if total_charged + amount > target_debt + 2000:
                amount = target_debt - total_charged

            if amount <= 0:
                break

            charge, created = Charge.objects.get_or_create(
                resort=resort,
                unit=unit,
                year=2025,
                month=random.randint(1, 12),
                type=charge_type,
                defaults={
                    "amount": amount,
                    "status": Charge.Status.PUBLISHED,
                },
            )
            if created:
                total_charged += amount
                charges_created += 1
                charge_objects.append(charge)
            else:
                charge_objects.append(charge)
                total_charged += charge.amount

        self.stdout.write(self.style.SUCCESS(
            f"Charges ready: {charges_created} new, total debt = {total_charged:,.2f} EGP"
        ))

        # ── Step 3: Create 50-100 Payments across 3 days ─────────────────
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        days = [today - timedelta(days=3), today - timedelta(days=2), today - timedelta(days=1)]
        # Distribute: ~20 payments day 1, ~25 day 2, ~30 day 3
        day_counts = [random.randint(15, 22), random.randint(20, 28), random.randint(25, 32)]
        total_payments = sum(day_counts)

        self.stdout.write(f"Generating {total_payments} payments across 3 days: {day_counts}")

        # Collect charges that still have balance
        available_charges = list(
            Charge.objects.filter(resort=resort, status=Charge.Status.PUBLISHED)
        )
        random.shuffle(available_charges)

        # Track remaining balance per charge
        balances = {}
        for c in available_charges:
            paid = sum(a.amount for a in c.allocations.all())
            balances[c.id] = c.amount - paid

        receipt_counter = 5000
        total_paid_amount = Decimal("0.00")
        payments_created = 0
        allocations_created = 0

        for day_idx, (day, count) in enumerate(zip(days, day_counts)):
            for i in range(count):
                # Pick a random unit that has charges with remaining balance
                charges_with_balance = [
                    c for c in available_charges if balances.get(c.id, 0) > 0
                ]
                if not charges_with_balance:
                    self.stdout.write(self.style.WARNING("No more charges with balance!"))
                    break

                charge = random.choice(charges_with_balance)
                remaining = balances[charge.id]

                # Pay between 30% and 90% of remaining, or full if small
                if remaining <= 200:
                    pay_amount = remaining
                else:
                    pct = random.uniform(0.3, 0.9)
                    pay_amount = Decimal(str(round(float(remaining) * pct, 2)))
                    pay_amount = min(pay_amount, remaining)

                if pay_amount <= 0:
                    continue

                # Random time during the day
                hour = random.randint(8, 22)
                minute = random.randint(0, 59)
                paid_at = day.replace(hour=hour, minute=minute, second=random.randint(0, 59))

                receipt_counter += 1
                payment = Payment.objects.create(
                    resort=resort,
                    unit=charge.unit,
                    receipt_no=f"RCP-{receipt_counter}",
                    total_amount=pay_amount,
                    paid_at=paid_at,
                    notes=f"دفعة تجريبية - {charge.get_type_display()}",
                )

                PaymentAllocation.objects.create(
                    payment=payment,
                    charge=charge,
                    amount=pay_amount,
                )

                balances[charge.id] -= pay_amount
                total_paid_amount += pay_amount
                payments_created += 1
                allocations_created += 1

        remaining_debt = sum(v for v in balances.values() if v > 0)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS(f"  Payments created: {payments_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Allocations created: {allocations_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Total paid: {total_paid_amount:,.2f} EGP"))
        self.stdout.write(self.style.SUCCESS(f"  Original debt: {total_charged:,.2f} EGP"))
        self.stdout.write(self.style.SUCCESS(f"  Remaining debt: {remaining_debt:,.2f} EGP"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(
            f"\nView results at: /admin/daily-collections/?date={days[0].strftime('%Y-%m-%d')}"
        )
        self.stdout.write(
            f"                 /admin/daily-collections/?date={days[1].strftime('%Y-%m-%d')}"
        )
        self.stdout.write(
            f"                 /admin/daily-collections/?date={days[2].strftime('%Y-%m-%d')}"
        )
