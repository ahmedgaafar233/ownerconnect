import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from core.models import Resort, Unit, OwnerUnit
from users.models import User
from billing.models import Charge
from collections_app.models import Payment, PaymentAllocation

class Command(BaseCommand):
    help = "Seeds the database with Resorts, Owners, Units, Charges, and Payments."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Seeding data... This may take a moment."))

        with transaction.atomic():
            # 1. Create Resort
            resort, _ = Resort.objects.get_or_create(name="Delta Sharm Resort")
            self.stdout.write(f"Resort: {resort.name}")

            # 2. Create Owners
            owners_data = [
                {"phone": "01001234567", "password": "password123"},
                {"phone": "01201234567", "password": "password123"},
                {"phone": "01101234567", "password": "password123"},
                {"phone": "01501234567", "password": "password123"},
            ]
            owners = []
            for od in owners_data:
                user, created = User.objects.get_or_create(phone=od["phone"], defaults={"role": User.Role.OWNER})
                if created:
                    user.set_password(od["password"])
                    user.save()
                owners.append(user)
            self.stdout.write(f"Created/Loaded {len(owners)} Owners.")

            # 3. Create Units & Link to Owners (Generate 50 units)
            units = []
            for i in range(1, 51): # 50 Units
                building_no = f"{10 + (i // 10)}" # Buildings 10, 11, 12...
                unit_no = f"{100 + (i % 10)}"     # Unit 100, 101...
                unit_key = f"{building_no}/{unit_no}-{i}" # Unique key
                
                unit, _ = Unit.objects.get_or_create(
                    resort=resort,
                    unit_key=unit_key,
                    defaults={
                        "building_no": building_no,
                        "unit_no": unit_no
                    }
                )
                units.append(unit)
                
                # Link Owner (Round robin)
                owner = owners[i % len(owners)]
                OwnerUnit.objects.get_or_create(unit=unit, owner=owner)
            
            self.stdout.write(f"Created/Loaded {len(units)} Units and linked Owners.")

            # 4. Create Charges (Electricity & Water & Maintenance)
            # Create charges for the current year
            current_year = timezone.now().year
            charge_types = [
                (Charge.Type.ELECTRICITY, Decimal("500.00")),
                (Charge.Type.WATER, Decimal("150.00")),
                (Charge.Type.ANNUAL_MAINTENANCE, Decimal("1000.00")),
            ]

            charges = []
            for unit in units:
                for c_type, amount in charge_types:
                    # Create a charge for Jan & Feb
                    for month in [1, 2]:
                        charge, created = Charge.objects.get_or_create(
                            resort=resort,
                            unit=unit,
                            year=current_year,
                            month=month,
                            type=c_type,
                            defaults={
                                "amount": amount,
                                "status": Charge.Status.PUBLISHED
                            }
                        )
                        if created:
                            charges.append(charge)
            
            self.stdout.write(f"Created {len(charges)} Charges.")

            # 5. Create Payments
            # Simulate some payments today to show up in the report
            today = timezone.now().date()
            
            # Payment 1: Full payment for Unit 10/101 (Owner 0)
            u1 = units[0]
            u1_charges = Charge.objects.filter(unit=u1)
            total_u1 = sum(c.amount for c in u1_charges)
            
            if total_u1 > 0:
                p1 = Payment.objects.create(
                    resort=resort,
                    unit=u1,
                    receipt_no=f"REC-{random.randint(10000, 99999)}",
                    total_amount=total_u1, # Full payment
                    created_by=User.objects.filter(role=User.Role.SUPERADMIN).first() or owners[0], # Fallback
                    paid_at=timezone.now()
                )
                # Allocate
                for c in u1_charges:
                    PaymentAllocation.objects.create(payment=p1, charge=c, amount=c.amount)

            # Payment 2: Partial payment for Unit 10/102 (Owner 1)
            u2 = units[1]
            u2_charges = Charge.objects.filter(unit=u2)
            if u2_charges.exists():
                c = u2_charges.first()
                p2 = Payment.objects.create(
                    resort=resort,
                    unit=u2,
                    receipt_no=f"REC-{random.randint(10000, 99999)}",
                    total_amount=Decimal("200.00"), # Partial
                    created_by=User.objects.filter(role=User.Role.SUPERADMIN).first() or owners[0],
                    paid_at=timezone.now()
                )
                PaymentAllocation.objects.create(payment=p2, charge=c, amount=Decimal("200.00"))

            self.stdout.write(self.style.SUCCESS("Successfully seeded data!"))
