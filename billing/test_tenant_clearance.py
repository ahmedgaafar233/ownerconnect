from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import ClearanceStatement
from billing.receipts import generate_clearance_pdf
from core.models import OwnerUnit, Resort, Unit

User = get_user_model()


class TenantClearanceWordingTests(TestCase):
    def setUp(self):
        self.resort = Resort.objects.create(name="Delta")
        self.unit = Unit.objects.create(resort=self.resort, unit_key="B1/101")
        self.owner = User.objects.create_user(phone="+201000000001", fullname="Owen Owner", role=User.Role.OWNER, resort=self.resort)
        self.tenant = User.objects.create_user(phone="+201000000002", fullname="Tina Tenant", role=User.Role.TENANT, resort=self.resort)
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        OwnerUnit.objects.create(owner=self.tenant, unit=self.unit)

    def html_for(self, requester):
        statement = ClearanceStatement.objects.create(
            unit=self.unit, requested_by=requester, as_of_date=date(2026, 10, 6),
            total_due=Decimal("0"), total_paid=Decimal("0"), total_remaining=Decimal("0"), is_clear=True,
        )
        with mock.patch("weasyprint.HTML") as html_class:
            html_class.return_value.write_pdf.return_value = b"%PDF"
            generate_clearance_pdf(statement, [])
        return html_class.call_args.kwargs["string"]

    def test_a_tenants_clearance_names_the_tenant_and_speaks_of_their_lease_period(self):
        html = self.html_for(self.tenant)
        self.assertIn("Tenant Name / اسم المستأجر", html)
        self.assertIn("Tina Tenant", html)
        self.assertNotIn("Owen Owner", html)
        self.assertIn("لا توجد مستحقات مالية على المستأجر عن فترة الإيجار", html)

    def test_an_owners_clearance_is_unchanged(self):
        html = self.html_for(self.owner)
        self.assertIn("Owner Name / اسم المالك", html)
        self.assertIn("Owen Owner", html)
        self.assertIn("لا توجد مستحقات مالية على الوحدة", html)
