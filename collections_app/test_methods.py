from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from collections_app.models import PaymentMethod
from core.models import Resort
from core.testing import bearer_client

User = get_user_model()

URL = "/api/payment-methods/"


class PaymentMethodTests(TestCase):
    def setUp(self):
        self.resort = Resort.objects.create(name="Delta")
        self.owner = User.objects.create_user(phone="+201000000001", role=User.Role.OWNER, resort=self.resort)
        self.tenant = User.objects.create_user(phone="+201000000002", role=User.Role.TENANT, resort=self.resort)
        self.other = User.objects.create_user(phone="+201000000003", role=User.Role.OWNER, resort=self.resort)
        self.security = User.objects.create_user(phone="+201000000004", role=User.Role.SECURITY, resort=self.resort)

    def add(self, user=None, **body):
        return bearer_client(user or self.owner).post(URL, body, format="json")

    def wallet(self, phone="+20 100 000 0101", **extra):
        return self.add(kind="WALLET", wallet_provider="VODAFONE_CASH", wallet_phone=phone, **extra)

    # ── saving ───────────────────────────────────────────────────────────

    def test_a_wallet_a_instapay_address_and_fawry_can_be_saved(self):
        wallet = self.wallet()
        self.assertEqual(wallet.status_code, 201, wallet.content)
        self.assertEqual(wallet.json()["label"], "Vodafone Cash · +201000000101")  # the number is stored in E.164
        self.assertEqual(self.add(kind="INSTAPAY", instapay_address="ahmed.g@instapay").status_code, 201)
        self.assertEqual(self.add(kind="FAWRY").status_code, 201)
        kinds = [m["kind"] for m in bearer_client(self.owner).get(URL).json()]
        self.assertCountEqual(kinds, ["WALLET", "INSTAPAY", "FAWRY"])

    def test_the_first_method_is_the_default_and_a_later_one_only_if_asked(self):
        first = self.wallet().json()
        second = self.add(kind="FAWRY").json()
        self.assertTrue(first["is_default"])
        self.assertFalse(second["is_default"])
        third = self.add(kind="INSTAPAY", instapay_address="meme@instapay", make_default=True).json()
        self.assertTrue(third["is_default"])
        defaults = [m["id"] for m in bearer_client(self.owner).get(URL).json() if m["is_default"]]
        self.assertEqual(defaults, [third["id"]])  # always exactly one

    def test_a_bank_card_cannot_be_saved_here_and_no_card_data_is_accepted(self):
        response = self.add(kind="CARD", card_number="4242424242424242", cvv="123", expiry="12/30")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PaymentMethod.objects.count(), 0)
        # Nor does a card number ride along on a method that is accepted.
        ok = self.add(kind="FAWRY", card_number="4242424242424242")
        self.assertEqual(ok.status_code, 201)
        self.assertNotIn("4242", str(ok.json()))
        self.assertNotIn("4242", PaymentMethod.objects.get().label)

    def test_rejects_bad_numbers_and_addresses(self):
        for body, field in (
            ({"kind": "WALLET", "wallet_provider": "VODAFONE_CASH", "wallet_phone": "0100 000 0101"}, "wallet_phone"),
            ({"kind": "WALLET", "wallet_phone": "+201000000101"}, "wallet_provider"),
            ({"kind": "INSTAPAY", "instapay_address": "not an address"}, "instapay_address"),
            ({"kind": "INSTAPAY", "instapay_address": ""}, "instapay_address"),
        ):
            with self.subTest(field=field):
                response = self.add(**body)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(field, response.json())
        self.assertEqual(PaymentMethod.objects.count(), 0)

    def test_the_same_method_twice_and_too_many_are_refused(self):
        self.assertEqual(self.wallet().status_code, 201)
        self.assertEqual(self.wallet().status_code, 400)
        for i in range(9):
            self.assertEqual(self.wallet(f"+20100000{i:04d}").status_code, 201)
        over = self.wallet("+201000009999")
        self.assertEqual(over.status_code, 400)
        self.assertIn("10", over.json()["detail"])

    # ── managing ─────────────────────────────────────────────────────────

    def test_removing_the_default_hands_the_default_to_another(self):
        first = self.wallet().json()
        second = self.add(kind="FAWRY").json()
        self.assertEqual(bearer_client(self.owner).delete(f"{URL}{first['id']}/").status_code, 204)
        left = bearer_client(self.owner).get(URL).json()
        self.assertEqual([(m["id"], m["is_default"]) for m in left], [(second["id"], True)])

    def test_a_tenant_can_save_too(self):
        self.assertEqual(self.add(self.tenant, kind="FAWRY").status_code, 201)

    def test_staff_have_no_payment_methods(self):
        self.assertEqual(bearer_client(self.security).get(URL).status_code, 403)
        self.assertEqual(self.add(self.security, kind="FAWRY").status_code, 403)

    # ── nobody else's ────────────────────────────────────────────────────

    def test_nobody_sees_or_touches_anyone_elses_methods(self):
        mine = self.wallet().json()
        theirs = self.add(self.other, kind="FAWRY").json()
        self.assertEqual([m["id"] for m in bearer_client(self.owner).get(URL).json()], [mine["id"]])
        client = bearer_client(self.owner)
        self.assertEqual(client.delete(f"{URL}{theirs['id']}/").status_code, 404)
        self.assertEqual(client.post(f"{URL}{theirs['id']}/default/").status_code, 404)
        self.assertTrue(PaymentMethod.objects.filter(pk=theirs["id"]).exists())

    # ── what can be added ────────────────────────────────────────────────

    def test_cards_are_offered_only_once_the_gateway_is_linked(self):
        with override_settings(PAYMOB_API_KEY="", PAYMOB_IFRAME_ID=""):
            options = bearer_client(self.owner).get(f"{URL}options/").json()
        self.assertFalse(options["card"]["enabled"])
        self.assertEqual(options["card"]["reason"], "GATEWAY_NOT_LINKED")
        self.assertTrue(options["wallet"]["enabled"])
        self.assertIn("VODAFONE_CASH", [p["value"] for p in options["wallet"]["providers"]])

        # A placeholder left in the settings isn't a linked account either.
        with override_settings(PAYMOB_API_KEY="replace-with-real-key", PAYMOB_IFRAME_ID="replace-me"):
            placeholder = bearer_client(self.owner).get(f"{URL}options/").json()
        self.assertFalse(placeholder["card"]["enabled"])

        with override_settings(PAYMOB_API_KEY="ZXlKaGJHY2lPaUpJVXpV", PAYMOB_IFRAME_ID="812345"):
            linked = bearer_client(self.owner).get(f"{URL}options/").json()
        self.assertTrue(linked["card"]["enabled"])
