import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from billing.models import Charge
from collections_app.models import Payment, PaymentAllocation
from core.models import Lease, Notification, OwnerUnit, Resort, Unit
from core.testing import bearer_client
from support.models import VisitorPass

User = get_user_model()

LEASES_URL = "/api/owner/leases/"
TEMP_MEDIA = tempfile.mkdtemp(prefix="lease-test-media-")


def png(name="id.png"):
    buf = BytesIO()
    Image.new("RGB", (12, 12), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def shift(day, months):
    """(year, month) `months` away from `day`'s month."""
    index = day.month - 1 + months
    return day.year + index // 12, index % 12 + 1


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class LeaseBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()  # the lease throttle counts per user and the cache outlives a test
        self.today = timezone.localdate()
        self.resort = Resort.objects.create(name="Delta")
        self.other_resort = Resort.objects.create(name="Elsewhere")
        self.unit = Unit.objects.create(resort=self.resort, unit_key="B1/101")
        self.other_unit = Unit.objects.create(resort=self.resort, unit_key="B1/102")

        self.owner = User.objects.create_user(phone="+201000000001", role=User.Role.OWNER, resort=self.resort)
        self.stranger = User.objects.create_user(phone="+201000000002", role=User.Role.OWNER, resort=self.resort)
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        OwnerUnit.objects.create(owner=self.stranger, unit=self.other_unit)

        self.reception = User.objects.create_user(phone="+201000000010", role=User.Role.RECEPTION, resort=self.resort)
        self.security = User.objects.create_user(phone="+201000000011", role=User.Role.SECURITY, resort=self.resort)
        self.far_reception = User.objects.create_user(
            phone="+201000000012", role=User.Role.RECEPTION, resort=self.other_resort
        )

        # A lease that covers this calendar month and next.
        self.first = self.today.replace(day=1)
        next_year, next_month = shift(self.today, 1)
        last_of_next = (date(next_year, next_month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        self.last = last_of_next

    def payload(self, **overrides):
        data = {
            "unit": self.unit.id,
            "term": "LONG",
            "start_date": self.first.isoformat(),
            "end_date": self.last.isoformat(),
            "tenant_name": "Mona Tenant",
            "tenant_phone": "+201005550001",
            "tenant_national_id": "29001011234567",
            "tenant_id_photo": png(),
            "occupants": 3,
        }
        data.update(overrides)
        return data

    def register(self, **overrides):
        return bearer_client(self.owner).post(LEASES_URL, self.payload(**overrides), format="multipart")

    def started_days_ago(self, days):
        """Make the registered lease one that began `days` ago (registration itself can't be backdated)."""
        start = self.today - timedelta(days=days)
        Lease.objects.update(start_date=start)
        OwnerUnit.objects.filter(owner__role=User.Role.TENANT).update(lease_start_date=start)

    def charge(self, ctype, offset, amount="100.00", unit=None):
        year, month = shift(self.today, offset)
        return Charge.objects.create(
            resort=self.resort,
            unit=unit or self.unit,
            year=year,
            month=month,
            type=ctype,
            amount=Decimal(amount),
            status=Charge.Status.PUBLISHED,
        )

    def charge_ids(self, user):
        response = bearer_client(user).get("/api/charges/", {"page_size": 100})
        self.assertEqual(response.status_code, 200, response.content)
        return {row["id"] for row in response.json()["results"]}


class RegistrationTests(LeaseBase):
    def test_long_lease_creates_the_tenant_account_and_tells_the_village(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.content)

        tenant = User.objects.get(phone="+201005550001")
        self.assertEqual(tenant.role, User.Role.TENANT)
        self.assertEqual(tenant.resort, self.resort)
        self.assertEqual(tenant.fullname, "Mona Tenant")
        link = OwnerUnit.objects.get(owner=tenant, unit=self.unit)
        self.assertEqual((link.lease_start_date, link.lease_end_date), (self.first, self.last))

        lease = Lease.objects.get()
        self.assertEqual(lease.tenant, tenant)
        self.assertEqual(lease.landlord, self.owner)

        told = set(
            Notification.objects.filter(type=Notification.Type.LEASE_REGISTERED).values_list("user_id", flat=True)
        )
        self.assertEqual(told, {self.reception.id, self.security.id})  # not the owner, not another village

    def test_short_stay_is_only_a_record(self):
        response = self.register(term="SHORT")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(User.objects.filter(phone="+201005550001").exists())
        self.assertEqual(OwnerUnit.objects.filter(unit=self.unit).count(), 1)  # just the owner

        ids = {self.charge("ELECTRICITY", 0).id}
        self.assertEqual(self.charge_ids(self.owner), ids)  # nothing moved

    def test_rejects_bad_input(self):
        cases = {
            "end_date": self.payload(end_date=(self.first - timedelta(days=1)).isoformat()),
            "tenant_phone": self.payload(tenant_phone="0100 555 0001"),
            "tenant_name": self.payload(tenant_name="  "),
            "tenant_national_id": self.payload(tenant_national_id=""),
            "occupants": self.payload(occupants=0),
        }
        for field, data in cases.items():
            with self.subTest(field=field):
                response = bearer_client(self.owner).post(LEASES_URL, data, format="multipart")
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(field, response.json())
        self.assertEqual(Lease.objects.count(), 0)

    def test_cannot_backdate_a_lease_into_a_month_that_was_already_billed(self):
        last_month = (self.first - timedelta(days=1)).replace(day=1)
        response = self.register(start_date=last_month.isoformat())
        self.assertEqual(response.status_code, 400)
        self.assertIn("start_date", response.json())
        self.assertEqual(Lease.objects.count(), 0)

    def test_id_photo_is_required_and_must_be_an_image(self):
        data = self.payload()
        del data["tenant_id_photo"]
        self.assertEqual(bearer_client(self.owner).post(LEASES_URL, data, format="multipart").status_code, 400)
        fake = SimpleUploadedFile("id.png", b"not an image", content_type="image/png")
        response = bearer_client(self.owner).post(LEASES_URL, self.payload(tenant_id_photo=fake), format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_cannot_use_an_existing_owners_number(self):
        response = self.register(tenant_phone=self.stranger.phone)
        self.assertEqual(response.status_code, 400)
        self.assertIn("tenant_phone", response.json())
        self.stranger.refresh_from_db()
        self.assertEqual(self.stranger.role, User.Role.OWNER)  # untouched

    def test_cannot_rent_to_yourself(self):
        self.assertEqual(self.register(tenant_phone=self.owner.phone).status_code, 400)

    def test_a_bare_sign_in_account_is_taken_over(self):
        # Someone who opened the app once but was never linked to anything.
        ghost = User.objects.create_user(phone="+201005550001")
        self.assertEqual(self.register().status_code, 201)
        ghost.refresh_from_db()
        self.assertEqual((ghost.role, ghost.resort_id), (User.Role.TENANT, self.resort.id))

    def test_overlapping_leases_are_refused(self):
        self.assertEqual(self.register().status_code, 201)
        again = self.register(tenant_phone="+201005550002")
        self.assertEqual(again.status_code, 400)
        self.assertIn("start_date", again.json())

    def test_only_owners_of_the_unit_can_rent_it_out(self):
        tenant = User.objects.create_user(phone="+201005550003", role=User.Role.TENANT, resort=self.resort)
        OwnerUnit.objects.create(owner=tenant, unit=self.unit)
        denied = bearer_client(tenant).post(LEASES_URL, self.payload(), format="multipart")
        self.assertEqual(denied.status_code, 403)
        # An owner can't rent a unit that isn't theirs.
        theirs = bearer_client(self.stranger).post(LEASES_URL, self.payload(), format="multipart")
        self.assertEqual(theirs.status_code, 400)
        self.assertIn("unit", theirs.json())


class ChargeRuleTests(LeaseBase):
    def setUp(self):
        super().setUp()
        self.register()
        self.tenant = User.objects.get(phone="+201005550001")
        self.in_window = self.charge("ELECTRICITY", 0)
        self.water_next = self.charge("WATER", 1)
        self.before = self.charge("ELECTRICITY", -1)
        self.after = self.charge("WATER", 2)
        self.maintenance = self.charge("ANNUAL_MAINTENANCE", 0)

    def test_utilities_move_to_the_tenant_while_the_lease_runs(self):
        owner_sees = self.charge_ids(self.owner)
        self.assertEqual(owner_sees, {self.before.id, self.after.id, self.maintenance.id})
        self.assertEqual(self.charge_ids(self.tenant), {self.in_window.id, self.water_next.id})

    def test_after_the_lease_the_owner_gets_them_back_but_the_tenant_keeps_paying_their_own(self):
        Lease.objects.update(start_date=self.first - timedelta(days=90), end_date=self.today - timedelta(days=1))
        # Window is now (start month .. yesterday's month): in_window + before fall in it, the rest don't.
        OwnerUnit.objects.filter(owner=self.tenant).update(
            lease_start_date=self.first - timedelta(days=90), lease_end_date=self.today - timedelta(days=1)
        )
        owner_sees = self.charge_ids(self.owner)
        self.assertEqual(owner_sees, {c.id for c in (self.in_window, self.water_next, self.before, self.after, self.maintenance)})
        tenant_sees = self.charge_ids(self.tenant)
        self.assertIn(self.before.id, tenant_sees)
        self.assertNotIn(self.after.id, tenant_sees)  # never the next occupant's months

    def test_tenant_balance_and_cleared_flag_follow_payments(self):
        data = bearer_client(self.owner).get(LEASES_URL).json()[0]
        self.assertEqual(data["tenant_balance"], "200.00")
        self.assertFalse(data["tenant_cleared"])

        payment = Payment.objects.create(resort=self.resort, unit=self.unit, receipt_no="R-1", total_amount=Decimal("200.00"))
        for charge in (self.in_window, self.water_next):
            PaymentAllocation.objects.create(payment=payment, charge=charge, amount=charge.amount)

        data = bearer_client(self.owner).get(LEASES_URL).json()[0]
        self.assertEqual(data["tenant_balance"], "0.00")
        self.assertTrue(data["tenant_cleared"])

    def test_clearance_for_the_tenant_covers_only_their_months(self):
        client = bearer_client(self.tenant)
        response = client.post("/api/clearance/generate/", {"unit": self.unit.id}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertFalse(body["is_clear"])
        # As of today: this month's electricity only — next month isn't due yet,
        # and the earlier/later months and the maintenance charge aren't theirs.
        self.assertEqual(body["total_due"], "100.00")

    def test_payments_follow_the_same_visibility(self):
        url = "/api/payments/initiate/"
        tenant_pay = bearer_client(self.tenant).post(url, {"charge_ids": [self.in_window.id]}, format="json")
        self.assertEqual(tenant_pay.status_code, 200, tenant_pay.content)
        # Not theirs: outside the lease months, or a non-utility charge.
        for charge in (self.before, self.maintenance):
            denied = bearer_client(self.tenant).post(url, {"charge_ids": [charge.id]}, format="json")
            self.assertEqual(denied.status_code, 404, charge.type)
        # And the owner can't pay the months that moved away.
        moved = bearer_client(self.owner).post(url, {"charge_ids": [self.in_window.id]}, format="json")
        self.assertEqual(moved.status_code, 404)
        own = bearer_client(self.owner).post(url, {"charge_ids": [self.maintenance.id]}, format="json")
        self.assertEqual(own.status_code, 200, own.content)


class EndingTests(LeaseBase):
    def test_ending_a_running_lease_stops_it_yesterday(self):
        self.register()
        self.started_days_ago(5)
        lease = Lease.objects.get()
        response = bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/")
        self.assertEqual(response.status_code, 200, response.content)
        yesterday = self.today - timedelta(days=1)
        lease.refresh_from_db()
        self.assertEqual(lease.end_date, yesterday)
        link = OwnerUnit.objects.get(owner=lease.tenant, unit=self.unit)
        self.assertEqual(link.lease_end_date, yesterday)  # the link stays: the tenant can still pay and clear
        self.assertEqual(response.json()["status"], "ENDED")
        self.assertTrue(Notification.objects.filter(user=lease.tenant, type=Notification.Type.LEASE_ENDED).exists())

    def test_cancelling_a_lease_that_has_not_started_removes_the_tenant_link(self):
        start = self.today + timedelta(days=10)
        self.register(start_date=start.isoformat(), end_date=(start + timedelta(days=30)).isoformat())
        lease = Lease.objects.get()
        self.assertEqual(bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/").status_code, 200)
        lease.refresh_from_db()
        self.assertIsNotNone(lease.cancelled_at)
        self.assertFalse(OwnerUnit.objects.filter(owner=lease.tenant, unit=self.unit).exists())

    def test_someone_elses_lease_is_a_404_and_ending_twice_a_409(self):
        self.register()
        lease = Lease.objects.get()
        self.assertEqual(bearer_client(self.stranger).post(f"{LEASES_URL}{lease.id}/end/").status_code, 404)
        self.assertEqual(bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/").status_code, 200)
        self.assertEqual(bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/").status_code, 409)

    def test_an_ended_tenant_can_no_longer_make_requests_but_still_sees_their_unit(self):
        self.register()
        self.started_days_ago(40)
        lease = Lease.objects.get()
        bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/")
        tenant = lease.tenant

        ticket = bearer_client(tenant).post(
            "/api/owner/tickets/",
            {"unit": self.unit.id, "category": "MAINTENANCE", "priority": "MEDIUM", "subject": "Leak", "description": ""},
            format="json",
        )
        self.assertEqual(ticket.status_code, 400)
        self.assertIn("unit", ticket.json())

        me = bearer_client(tenant).get("/api/me/").json()
        self.assertEqual([u["unit_key"] for u in me["units"]], ["B1/101"])
        self.assertEqual(me["units"][0]["lease"]["status"], "ENDED")


class VisibilityTests(LeaseBase):
    def test_me_shows_the_owner_their_tenant_and_the_tenant_their_window(self):
        self.register()
        me = bearer_client(self.owner).get("/api/me/").json()
        unit = next(u for u in me["units"] if u["id"] == self.unit.id)
        self.assertEqual(unit["relation"], "OWNER")
        self.assertEqual(unit["lease"]["tenant_name"], "Mona Tenant")
        self.assertEqual(unit["lease"]["status"], "ACTIVE")

        tenant = User.objects.get(phone="+201005550001")
        mine = bearer_client(tenant).get("/api/me/").json()["units"][0]
        self.assertEqual(mine["relation"], "TENANT")
        self.assertEqual(mine["lease"]["end_date"], self.last.isoformat())
        self.assertNotIn("tenant_name", mine["lease"])  # not the owner's private record

    def test_an_ended_rental_stays_on_the_card_while_the_tenant_still_owes(self):
        self.register()
        self.started_days_ago(200)
        # Ended long ago, so only the unpaid balance keeps it visible.
        Lease.objects.update(end_date=self.today - timedelta(days=150))
        owed = self.charge("WATER", -6)  # a month inside the (200-day-old) window
        Lease.objects.update(start_date=self.today - timedelta(days=200))
        unit = bearer_client(self.owner).get("/api/me/").json()["units"][0]
        self.assertEqual(unit["lease"]["status"], "ENDED")
        self.assertFalse(unit["lease"]["tenant_cleared"])

        payment = Payment.objects.create(resort=self.resort, unit=self.unit, receipt_no="R-9", total_amount=owed.amount)
        PaymentAllocation.objects.create(payment=payment, charge=owed, amount=owed.amount)
        unit = bearer_client(self.owner).get("/api/me/").json()["units"][0]
        self.assertIsNone(unit["lease"])  # settled and old: off the card

    def test_a_recently_ended_rental_shows_as_cleared(self):
        self.register()
        self.started_days_ago(10)
        lease = Lease.objects.get()
        bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/")
        unit = bearer_client(self.owner).get("/api/me/").json()["units"][0]
        self.assertEqual(unit["lease"]["status"], "ENDED")
        self.assertTrue(unit["lease"]["tenant_cleared"])  # nothing was ever billed to them

    def test_strangers_see_none_of_it(self):
        self.register()
        self.assertEqual(bearer_client(self.stranger).get(LEASES_URL).json(), [])
        other = bearer_client(self.stranger).get("/api/me/").json()["units"][0]
        self.assertIsNone(other["lease"])

    def test_security_sees_the_tenant_when_the_owner_asks_for_cards(self):
        self.register()
        VisitorPass.objects.create(
            resort=self.resort,
            unit=self.unit,
            owner=self.owner,
            pass_type=VisitorPass.PassType.BEACH_ACCESS,
            visitor_name="Family",
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=3),
            status=VisitorPass.Status.PENDING,
        )
        rows = bearer_client(self.security).get("/api/staff/passes/requests/").json()
        rows = rows["results"] if isinstance(rows, dict) else rows
        self.assertEqual(rows[0]["unit_lease"]["tenant_name"], "Mona Tenant")
        self.assertEqual(rows[0]["unit_lease"]["tenant_phone"], "+201005550001")

    def test_id_photo_is_only_for_the_villages_own_front_desk(self):
        self.register()
        lease = Lease.objects.get()
        url = f"/admin/lease-id/{lease.id}/"

        self.client.force_login(self.reception)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.far_reception)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.security)  # not admin staff at all
        self.assertNotEqual(self.client.get(url).status_code, 200)

        self.client.logout()
        self.assertNotEqual(self.client.get(url).status_code, 200)


class AdminActionTests(LeaseBase):
    def test_the_front_desk_can_end_a_rental_registered_by_mistake(self):
        from django.contrib import admin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from core.admin import LeaseAdmin

        self.register()
        lease = Lease.objects.get()

        request = RequestFactory().post("/admin/core/lease/")
        request.user = self.reception
        request.session = {}
        request._messages = FallbackStorage(request)
        model_admin = LeaseAdmin(Lease, admin.site)
        model_admin.end_selected_rentals(request, Lease.objects.filter(pk=lease.pk))

        lease.refresh_from_db()
        self.assertTrue(lease.cancelled_at or lease.end_date < self.today)
        self.assertTrue(Notification.objects.filter(user=lease.tenant, type=Notification.Type.LEASE_ENDED).exists())


SCAN_URL = "/api/staff/passes/scan/"


class AccessPassTests(LeaseBase):
    """Every adult staying in a rented unit holds a gate-and-pool QR for the length of the rental."""

    def setUp(self):
        super().setUp()
        self.recreation = User.objects.create_user(
            phone="+201000000013", role=User.Role.RECREATION, resort=self.resort
        )

    def scan(self, user, code):
        response = bearer_client(user).post(SCAN_URL, {"pass_code": code}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def adult(self, lease, name="Mona Spouse", **overrides):
        data = {"full_name": name, "national_id": "29001019999999", "relation": "SPOUSE", "id_photo": png("a.png")}
        data.update(overrides)
        return bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/adults/", data, format="multipart")

    def make_unit_small(self, allowance=2):
        from core.models import UnitType

        self.unit.unit_type = UnitType.objects.create(resort=self.resort, name="Studio", card_allowance=allowance)
        self.unit.save()

    # ── issuing ──────────────────────────────────────────────────────────

    def test_a_long_tenant_gets_a_qr_valid_for_the_rental_and_sees_it_in_the_app(self):
        data = self.register().json()
        lease = Lease.objects.get()
        code = data["access"]["pass_code"]
        self.assertEqual(lease.access_pass.pass_code, code)
        self.assertEqual(lease.access_pass.pass_type, "TENANT")
        self.assertEqual(lease.access_pass.owner, lease.tenant)

        starts, ends = timezone.localtime(lease.access_pass.valid_from), timezone.localtime(lease.access_pass.valid_to)
        self.assertEqual((starts.date(), starts.hour), (self.first, 0))
        self.assertEqual((ends.date(), ends.hour, ends.minute), (self.last, 23, 59))

        tenant_passes = bearer_client(lease.tenant).get("/api/owner/passes/").json()["results"]
        self.assertEqual([p["pass_code"] for p in tenant_passes], [code])

    def test_a_short_stay_has_no_account_so_the_owner_holds_the_qr_to_hand_over(self):
        self.register(term="SHORT")
        lease = Lease.objects.get()
        self.assertEqual(lease.access_pass.owner, self.owner)
        mine = bearer_client(self.owner).get("/api/owner/passes/").json()["results"]
        self.assertIn(lease.access_pass.pass_code, [p["pass_code"] for p in mine])

    def test_the_same_qr_opens_the_village_gate_and_the_pool(self):
        self.register()
        code = Lease.objects.get().access_pass.pass_code
        self.assertEqual(self.scan(self.security, code)["result"], "GRANTED")
        pool = self.scan(self.recreation, code)
        self.assertEqual(pool["result"], "GRANTED")
        self.assertEqual(pool["pass"]["pass_type"], "TENANT")

    def test_it_does_not_use_up_the_units_pool_cards(self):
        from support.models import VisitorPass

        self.make_unit_small(2)
        self.register()
        self.assertEqual(VisitorPass.active_cards(self.unit).count(), 0)

    # ── other adults ─────────────────────────────────────────────────────

    def test_each_further_adult_is_registered_and_gets_their_own_qr(self):
        self.register()
        lease = Lease.objects.get()
        response = self.adult(lease)
        self.assertEqual(response.status_code, 201, response.content)

        adults = response.json()["adults"]
        self.assertEqual([a["full_name"] for a in adults], ["Mona Spouse"])
        self.assertNotEqual(adults[0]["access"]["pass_code"], lease.access_pass.pass_code)
        self.assertEqual(self.scan(self.security, adults[0]["access"]["pass_code"])["result"], "GRANTED")
        # They are the tenant's to show, in the tenant's own app.
        codes = [p["pass_code"] for p in bearer_client(lease.tenant).get("/api/owner/passes/").json()["results"]]
        self.assertIn(adults[0]["access"]["pass_code"], codes)

    def test_a_unit_only_has_room_for_as_many_adults_as_its_size_allows(self):
        self.make_unit_small(2)  # the tenant and one more
        self.register()
        lease = Lease.objects.get()
        self.assertEqual(self.adult(lease, "First").status_code, 201)
        second = self.adult(lease, "Second")
        self.assertEqual(second.status_code, 400)
        self.assertIn("full_name", second.json())
        self.assertEqual(lease.adults.count(), 1)

    def test_removing_an_adult_stops_their_qr_and_deletes_their_id(self):
        self.register()
        lease = Lease.objects.get()
        data = self.adult(lease).json()
        adult = lease.adults.get()
        path = adult.id_photo.path
        code = data["adults"][0]["access"]["pass_code"]

        response = bearer_client(self.owner).delete(f"{LEASES_URL}{lease.id}/adults/{adult.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["adults"], [])
        result = self.scan(self.security, code)
        self.assertEqual((result["result"], result["reason"]), ("DENIED", "CANCELLED"))
        import os

        self.assertFalse(os.path.exists(path))

    def test_adults_cannot_be_added_to_a_rental_that_is_over(self):
        self.register()
        lease = Lease.objects.get()
        Lease.objects.update(start_date=self.today - timedelta(days=20), end_date=self.today - timedelta(days=2))
        self.assertEqual(self.adult(lease).status_code, 400)

    def test_marriage_certificates_and_passports_can_be_added_and_removed(self):
        self.register()
        lease = Lease.objects.get()
        client = bearer_client(self.owner)
        response = client.post(
            f"{LEASES_URL}{lease.id}/documents/",
            {"kind": "MARRIAGE_CERT", "file": png("m.png")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual([d["kind"] for d in response.json()["documents"]], ["MARRIAGE_CERT"])
        doc = lease.documents.get()
        gone = client.delete(f"{LEASES_URL}{lease.id}/documents/{doc.id}/")
        self.assertEqual(gone.json()["documents"], [])

    # ── extending ────────────────────────────────────────────────────────

    def test_extending_keeps_the_same_qr_valid_through_the_extra_time(self):
        self.register()
        lease = Lease.objects.get()
        spouse = self.adult(lease).json()["adults"][0]["access"]["pass_code"]
        code = lease.access_pass.pass_code
        new_end = self.last + timedelta(days=30)

        response = bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/extend/", {"end_date": new_end.isoformat()}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["end_date"], new_end.isoformat())
        self.assertEqual(response.json()["access"]["pass_code"], code)  # the very same QR

        lease.refresh_from_db()
        self.assertEqual(timezone.localtime(lease.access_pass.valid_to).date(), new_end)
        for pass_code in (code, spouse):
            self.assertEqual(self.scan(self.security, pass_code)["result"], "GRANTED")
        # and the tenant's own window follows, so they can still see/pay the added months
        link = OwnerUnit.objects.get(owner=lease.tenant, unit=self.unit)
        self.assertEqual(link.lease_end_date, new_end)

    def test_an_extension_must_go_forward_and_must_not_run_into_another_rental(self):
        self.register()
        lease = Lease.objects.get()
        client = bearer_client(self.owner)
        back = client.post(f"{LEASES_URL}{lease.id}/extend/", {"end_date": self.first.isoformat()}, format="json")
        self.assertEqual(back.status_code, 400)

        later = self.last + timedelta(days=10)
        Lease.objects.create(
            resort=self.resort, unit=self.unit, landlord=self.owner, term="SHORT",
            start_date=later, end_date=later + timedelta(days=5), tenant_name="Next", tenant_phone="+201005550009",
            tenant_national_id="1", tenant_id_photo="x.png", occupants=1,
        )
        clash = client.post(
            f"{LEASES_URL}{lease.id}/extend/", {"end_date": (later + timedelta(days=1)).isoformat()}, format="json"
        )
        self.assertEqual(clash.status_code, 400)

    # ── renewing ─────────────────────────────────────────────────────────

    def ended_lease(self):
        self.register()
        lease = Lease.objects.get()
        self.adult(lease)
        bearer_client(self.owner).post(
            f"{LEASES_URL}{lease.id}/documents/", {"kind": "PASSPORT", "file": png("p.png")}, format="multipart"
        )
        start, end = self.today - timedelta(days=60), self.today - timedelta(days=2)
        Lease.objects.update(start_date=start, end_date=end)
        OwnerUnit.objects.filter(owner=lease.tenant, unit=self.unit).update(lease_start_date=start, lease_end_date=end)
        lease.refresh_from_db()
        from core.leases import passes_of, _sync_pass

        for visitor_pass in passes_of(lease):
            _sync_pass(visitor_pass)
        return lease

    def test_renewing_a_finished_rental_brings_back_the_same_qrs_for_the_new_period(self):
        lease = self.ended_lease()
        from core.leases import passes_of

        codes = [p.pass_code for p in passes_of(lease)]
        self.assertEqual(self.scan(self.security, codes[0])["reason"], "EXPIRED")

        end = self.today + timedelta(days=45)
        response = bearer_client(self.owner).post(
            f"{LEASES_URL}{lease.id}/renew/",
            {"start_date": self.today.isoformat(), "end_date": end.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        new = Lease.objects.get(pk=response.json()["id"])
        self.assertNotEqual(new.pk, lease.pk)

        self.assertEqual(new.access_pass_id, lease.access_pass_id)  # same QR
        self.assertEqual([a.full_name for a in new.adults.all()], ["Mona Spouse"])
        self.assertEqual([d.kind for d in new.documents.all()], ["PASSPORT"])
        for code in codes:
            self.assertEqual(self.scan(self.security, code)["result"], "GRANTED")
        # separate copies of the files, so deleting from one rental can't break the other
        self.assertNotEqual(new.tenant_id_photo.path, lease.tenant_id_photo.path)

        link = OwnerUnit.objects.get(owner=new.tenant, unit=self.unit)
        self.assertEqual(link.lease_end_date, end)
        lease.refresh_from_db()
        self.assertEqual(lease.end_date, self.today - timedelta(days=2))  # the old record is untouched

    def test_a_running_rental_can_only_be_followed_straight_on(self):
        self.register()
        lease = Lease.objects.get()
        client = bearer_client(self.owner)
        gap = client.post(
            f"{LEASES_URL}{lease.id}/renew/",
            {"start_date": (self.last + timedelta(days=20)).isoformat(), "end_date": (self.last + timedelta(days=50)).isoformat()},
            format="json",
        )
        self.assertEqual(gap.status_code, 400)
        self.assertIn("start_date", gap.json())

        straight = client.post(
            f"{LEASES_URL}{lease.id}/renew/",
            {"start_date": (self.last + timedelta(days=1)).isoformat(), "end_date": (self.last + timedelta(days=40)).isoformat()},
            format="json",
        )
        self.assertEqual(straight.status_code, 201, straight.content)
        # one QR, valid from the first rental's start to the renewal's end — no gap in between
        lease.refresh_from_db()
        valid_from = timezone.localtime(lease.access_pass.valid_from).date()
        valid_to = timezone.localtime(lease.access_pass.valid_to).date()
        self.assertEqual((valid_from, valid_to), (self.first, self.last + timedelta(days=40)))

    def test_renewing_as_a_short_stay_hands_the_qrs_back_to_the_owner(self):
        lease = self.ended_lease()
        end = self.today + timedelta(days=10)
        response = bearer_client(self.owner).post(
            f"{LEASES_URL}{lease.id}/renew/",
            {"start_date": self.today.isoformat(), "end_date": end.isoformat(), "term": "SHORT"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        new = Lease.objects.get(pk=response.json()["id"])
        self.assertIsNone(new.tenant)
        self.assertEqual(new.access_pass.owner, self.owner)

    # ── ending ───────────────────────────────────────────────────────────

    def test_ending_a_rental_early_stops_its_qrs(self):
        self.register()
        lease = Lease.objects.get()
        self.started_days_ago(5)
        code = lease.access_pass.pass_code
        self.assertEqual(self.scan(self.security, code)["result"], "GRANTED")
        bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/")
        result = self.scan(self.security, code)
        self.assertEqual((result["result"], result["reason"]), ("DENIED", "EXPIRED"))

    def test_cancelling_a_rental_that_never_started_cancels_its_qrs(self):
        start = self.today + timedelta(days=10)
        self.register(start_date=start.isoformat(), end_date=(start + timedelta(days=30)).isoformat())
        lease = Lease.objects.get()
        code = lease.access_pass.pass_code
        bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/")
        result = self.scan(self.security, code)
        self.assertEqual((result["result"], result["reason"]), ("DENIED", "CANCELLED"))

    # ── who may do any of this ───────────────────────────────────────────

    def test_only_the_owner_of_the_rental_may_change_it(self):
        self.register()
        lease = Lease.objects.get()
        tenant = lease.tenant
        for who, expected in ((self.stranger, 404), (tenant, 403)):
            client = bearer_client(who)
            for url, body in (
                (f"{LEASES_URL}{lease.id}/extend/", {"end_date": (self.last + timedelta(days=5)).isoformat()}),
                (f"{LEASES_URL}{lease.id}/renew/", {"start_date": self.today.isoformat(), "end_date": self.last.isoformat()}),
            ):
                with self.subTest(who=who.phone, url=url):
                    self.assertEqual(client.post(url, body, format="json").status_code, expected)
            adult = client.post(
                f"{LEASES_URL}{lease.id}/adults/",
                {"full_name": "X", "national_id": "1", "id_photo": png()},
                format="multipart",
            )
            self.assertEqual(adult.status_code, expected)


STAFF_LEASES_URL = "/api/staff/leases/"


class SecurityRegistryTests(LeaseBase):
    """Security registers the tenants: who they are, who is with them, and every paper the owner sent."""

    def setUp(self):
        super().setUp()
        self.far_security = User.objects.create_user(
            phone="+201000000014", role=User.Role.SECURITY, resort=self.other_resort
        )
        self.register()
        self.lease = Lease.objects.get()
        client = bearer_client(self.owner)
        client.post(
            f"{LEASES_URL}{self.lease.id}/adults/",
            {"full_name": "Mona Spouse", "national_id": "29001019999999", "relation": "SPOUSE", "id_photo": png("a.png")},
            format="multipart",
        )
        client.post(
            f"{LEASES_URL}{self.lease.id}/documents/",
            {"kind": "MARRIAGE_CERT", "file": png("m.png")},
            format="multipart",
        )

    def listing(self, user, **params):
        response = bearer_client(user).get(STAFF_LEASES_URL, params)
        return response

    def test_security_sees_the_tenant_everyone_with_them_and_the_papers(self):
        response = self.listing(self.security)
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()["results"][0]
        self.assertEqual((row["unit_key"], row["tenant_name"], row["tenant_national_id"]), ("B1/101", "Mona Tenant", "29001011234567"))
        self.assertEqual(row["status"], "ACTIVE")
        self.assertEqual([(a["full_name"], a["national_id"]) for a in row["adults"]], [("Mona Spouse", "29001019999999")])
        self.assertEqual([d["kind"] for d in row["documents"]], ["MARRIAGE_CERT"])
        for url in (row["id_photo_url"], row["adults"][0]["id_photo_url"], row["documents"][0]["url"]):
            self.assertTrue(url.startswith("http"), url)

    def test_each_paper_can_be_opened_by_security_of_that_village_only(self):
        row = self.listing(self.security).json()["results"][0]
        for url in (row["id_photo_url"], row["adults"][0]["id_photo_url"], row["documents"][0]["url"]):
            path = url.split("testserver", 1)[1]
            with self.subTest(path=path):
                ok = bearer_client(self.security).get(path)
                self.assertEqual(ok.status_code, 200)
                self.assertTrue(b"".join(ok.streaming_content).startswith(b"\x89PNG"))
                self.assertEqual(bearer_client(self.far_security).get(path).status_code, 404)  # another village
                self.assertEqual(bearer_client(self.owner).get(path).status_code, 403)        # not staff
                self.assertEqual(bearer_client(self.reception).get(path).status_code, 403)    # the admin has its own view
                from rest_framework.test import APIClient

                self.assertEqual(APIClient().get(path).status_code, 401)

    def test_only_security_may_list(self):
        recreation = User.objects.create_user(phone="+201000000015", role=User.Role.RECREATION, resort=self.resort)
        for who, code in ((self.owner, 403), (recreation, 403), (self.reception, 403), (self.security, 200)):
            with self.subTest(who=who.role):
                self.assertEqual(self.listing(who).status_code, code)

    def test_security_of_another_village_sees_nothing(self):
        self.assertEqual(self.listing(self.far_security).json()["results"], [])

    def test_finished_and_cancelled_rentals_are_filtered(self):
        Lease.objects.update(start_date=self.today - timedelta(days=60), end_date=self.today - timedelta(days=2))
        self.assertEqual(self.listing(self.security).json()["results"], [])  # default: running or coming
        ended = self.listing(self.security, status="ENDED").json()["results"]
        self.assertEqual(len(ended), 1)
        Lease.objects.update(cancelled_at=timezone.now())
        self.assertEqual(self.listing(self.security, status="ENDED").json()["results"], [])

    def test_search_by_unit_or_tenant_name(self):
        self.assertEqual(len(self.listing(self.security, q="mona").json()["results"]), 1)
        self.assertEqual(len(self.listing(self.security, q="101").json()["results"]), 1)
        self.assertEqual(len(self.listing(self.security, q="nobody").json()["results"]), 0)

    def test_the_front_desk_opens_the_same_papers_through_the_admin(self):
        adult = self.lease.adults.get()
        document = self.lease.documents.get()
        for url in (f"/admin/lease-adult-id/{adult.id}/", f"/admin/lease-document/{document.id}/"):
            with self.subTest(url=url):
                self.client.force_login(self.reception)
                self.assertEqual(self.client.get(url).status_code, 200)
                self.client.force_login(self.far_reception)
                self.assertEqual(self.client.get(url).status_code, 404)


class MeterReadingTests(LeaseBase):
    """Maintenance reads the meters; entry and exit readings belong to the rental."""

    def setUp(self):
        super().setUp()
        self.maintenance = User.objects.create_user(phone="+201000000016", role=User.Role.MAINTENANCE, resort=self.resort)
        self.far_maintenance = User.objects.create_user(
            phone="+201000000017", role=User.Role.MAINTENANCE, resort=self.other_resort
        )

    def reading(self, meter="ELECTRICITY", kind="ENTRY", value="1500.50", on=None, unit=None):
        from core.models import MeterReading

        return MeterReading.objects.create(
            resort=self.resort, unit=unit or self.unit, meter=meter, kind=kind, reading=Decimal(value),
            read_on=on or self.first, recorded_by=self.maintenance,
        )

    def test_maintenance_is_asked_for_the_entry_reading_when_a_rental_is_registered(self):
        self.register()
        due = Notification.objects.filter(type=Notification.Type.METER_READING_DUE)
        self.assertEqual([n.user_id for n in due], [self.maintenance.id])  # not the other village's team
        self.assertIn("entry", due.get().body)
        self.assertIn("B1/101", due.get().body)

    def test_and_for_the_exit_reading_when_it_ends(self):
        self.register()
        self.started_days_ago(5)
        lease = Lease.objects.get()
        Notification.objects.all().delete()
        bearer_client(self.owner).post(f"{LEASES_URL}{lease.id}/end/")
        due = Notification.objects.filter(type=Notification.Type.METER_READING_DUE)
        self.assertEqual(due.count(), 1)
        self.assertIn("exit", due.get().body)

    def test_a_reading_attaches_itself_to_the_rental_its_date_falls_in(self):
        self.register()
        lease = Lease.objects.get()
        inside = self.reading(on=self.first)
        self.assertEqual(inside.lease, lease)
        far = self.reading(on=self.first - timedelta(days=60))
        self.assertIsNone(far.lease)
        elsewhere = self.reading(unit=self.other_unit)
        self.assertIsNone(elsewhere.lease)

    def test_entry_and_exit_readings_show_on_the_rental_for_owner_tenant_and_security(self):
        self.register()
        lease = Lease.objects.get()
        self.reading("ELECTRICITY", "ENTRY", "1500.50")
        self.reading("WATER", "ENTRY", "320.00")
        self.reading("ELECTRICITY", "REGULAR", "1600.00", on=self.today)  # a routine reading isn't entry/exit

        owner_view = bearer_client(self.owner).get(LEASES_URL).json()[0]["meter_readings"]
        self.assertEqual(owner_view["ELECTRICITY"]["entry"]["reading"], "1500.50")
        self.assertEqual(owner_view["WATER"]["entry"]["reading"], "320.00")
        self.assertIsNone(owner_view["ELECTRICITY"]["exit"])

        tenant_unit = bearer_client(lease.tenant).get("/api/me/").json()["units"][0]
        self.assertEqual(tenant_unit["lease"]["meter_readings"]["ELECTRICITY"]["entry"]["reading"], "1500.50")

        staff = bearer_client(self.security).get(STAFF_LEASES_URL).json()["results"][0]["meter_readings"]
        self.assertEqual(staff["WATER"]["entry"]["reading"], "320.00")

    def test_who_may_record_and_see_readings_in_the_admin(self):
        from django.contrib import admin

        from core.admin import MeterReadingAdmin

        model_admin = MeterReadingAdmin(MeterReading_model(), admin.site)
        from django.test import RequestFactory

        def request_for(user):
            request = RequestFactory().get("/admin/core/meterreading/")
            request.user = user
            return request

        can = lambda user, perm: getattr(model_admin, perm)(request_for(user))
        self.assertTrue(can(self.maintenance, "has_add_permission"))
        self.assertTrue(can(self.reception, "has_view_permission"))
        self.assertFalse(can(self.reception, "has_add_permission"))  # front desk reads, Maintenance writes
        self.assertFalse(can(self.owner, "has_module_permission"))
        self.assertFalse(can(self.security, "has_module_permission"))
        self.assertFalse(can(self.maintenance, "has_delete_permission"))

    def test_maintenance_only_sees_and_picks_units_from_their_own_village(self):
        from django.contrib import admin
        from django.test import RequestFactory

        from core.admin import MeterReadingAdmin

        self.reading()
        model_admin = MeterReadingAdmin(MeterReading_model(), admin.site)
        request = RequestFactory().get("/admin/core/meterreading/")
        request.user = self.far_maintenance
        self.assertEqual(model_admin.get_queryset(request).count(), 0)
        request.user = self.maintenance
        self.assertEqual(model_admin.get_queryset(request).count(), 1)


def MeterReading_model():
    from core.models import MeterReading

    return MeterReading
