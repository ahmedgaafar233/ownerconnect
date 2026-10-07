from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import Charge
from collections_app.models import Payment
from collections_app.payers import payer_snapshot
from collections_app.receipts import _payer_for, generate_receipt_pdf
from core.models import OwnerUnit, Resort, Unit

User = get_user_model()


class PayerTests(TestCase):
    def setUp(self):
        self.resort = Resort.objects.create(name="Delta")
        self.unit = Unit.objects.create(resort=self.resort, unit_key="B1/101")
        self.other_unit = Unit.objects.create(resort=self.resort, unit_key="B1/102")

        self.owner = User.objects.create_user(
            phone="+201000000001", fullname="Owen Owner", role=User.Role.OWNER, resort=self.resort
        )
        self.tenant = User.objects.create_user(
            phone="+201000000002", fullname="Tina Tenant", role=User.Role.TENANT, resort=self.resort
        )
        self.stranger = User.objects.create_user(
            phone="+201000000003", fullname="Sam Stranger", role=User.Role.OWNER, resort=self.resort
        )
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        OwnerUnit.objects.create(owner=self.tenant, unit=self.unit)
        OwnerUnit.objects.create(owner=self.stranger, unit=self.other_unit)

        self.finance = User.objects.create_user(
            phone="+201000000010", role=User.Role.FINANCIAL_MANAGER, resort=self.resort
        )
        Charge.objects.create(
            resort=self.resort, unit=self.unit, year=2026, month=10, type="WATER",
            amount=Decimal("100.00"), status=Charge.Status.PUBLISHED,
        )

    def record(self, **extra):
        self.client.force_login(self.finance)
        data = {"target_unit_id": self.unit.id, "receipt_no": "RCP-1", "amount_WATER": "100", **extra}
        with mock.patch("collections_app.views.generate_receipt_pdf"):
            response = self.client.post(f"/admin/record-payment/?unit_id={self.unit.id}", data)
        self.assertEqual(response.status_code, 200, response.content[:300])
        return Payment.objects.get()

    def test_staff_can_record_that_the_tenant_paid(self):
        payment = self.record(payer_id=self.tenant.id)
        self.assertEqual(payment.payer, self.tenant)
        self.assertEqual((payment.payer_name, payment.payer_role), ("Tina Tenant", "TENANT"))

    def test_without_a_choice_the_owner_is_the_payer(self):
        payment = self.record()
        self.assertEqual((payment.payer, payment.payer_name, payment.payer_role), (self.owner, "Owen Owner", "OWNER"))

    def test_someone_who_is_not_a_resident_of_the_unit_cannot_be_named_as_payer(self):
        payment = self.record(payer_id=self.stranger.id)
        self.assertEqual(payment.payer, self.owner)

    def test_the_form_offers_the_units_owner_and_tenant(self):
        self.client.force_login(self.finance)
        html = self.client.get(f"/admin/record-payment/?unit_id={self.unit.id}").content.decode()
        self.assertIn("Owen Owner", html)
        self.assertIn("Tina Tenant", html)
        self.assertNotIn("Sam Stranger", html)

    def test_the_receipt_says_who_it_was_received_from_and_in_what_capacity(self):
        payment = Payment.objects.create(
            resort=self.resort, unit=self.unit, receipt_no="R-1", total_amount=Decimal("100"), **payer_snapshot(self.tenant)
        )
        with mock.patch("weasyprint.HTML") as html_class:
            html_class.return_value.write_pdf.return_value = b"%PDF"
            generate_receipt_pdf(payment)
        html = html_class.call_args.kwargs["string"]
        self.assertIn("Received From", html)
        self.assertIn("استلمنا من", html)
        self.assertIn("Tina Tenant (Tenant / مستأجر)", html)
        self.assertNotIn("Owen Owner", html)

    def test_the_name_on_a_receipt_survives_the_person_being_renamed(self):
        payment = Payment.objects.create(
            resort=self.resort, unit=self.unit, receipt_no="R-2", total_amount=Decimal("1"), **payer_snapshot(self.tenant)
        )
        self.tenant.fullname = "Someone Else"
        self.tenant.save()
        self.assertEqual(_payer_for(payment), ("Tina Tenant", "TENANT"))

    def test_a_payment_from_before_payers_were_recorded_still_names_the_owner(self):
        payment = Payment.objects.create(resort=self.resort, unit=self.unit, receipt_no="R-3", total_amount=Decimal("1"))
        self.assertEqual(_payer_for(payment), ("Owen Owner", "OWNER"))
