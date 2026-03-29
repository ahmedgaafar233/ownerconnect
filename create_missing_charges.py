
import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.models import Unit, Resort
from billing.models import Charge

def create_charges():
    # Unit 8 (from previous context)
    unit = Unit.objects.get(id=8)
    print(f"Adding charges for Unit: {unit} (ID: {unit.id})")

    # 1. Create Water Charge
    Charge.objects.create(
        resort=unit.resort,
        unit=unit,
        type=Charge.Type.WATER,
        amount=Decimal("450.00"),
        year=2024,
        month=1,
        status=Charge.Status.PUBLISHED,
        notes="Water bill for Jan 2024"
    )
    print("Created Water Charge: 450.00")

    # 2. Create Annual Maintenance Charge
    Charge.objects.create(
        resort=unit.resort,
        unit=unit,
        type=Charge.Type.ANNUAL_MAINTENANCE,
        amount=Decimal("5000.00"),
        year=2024,
        month=None, # Annual
        status=Charge.Status.PUBLISHED,
        notes="Annual Maintenance 2024"
    )
    print("Created Annual Maintenance Charge: 5000.00")

if __name__ == "__main__":
    create_charges()
