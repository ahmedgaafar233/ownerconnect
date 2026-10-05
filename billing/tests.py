from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from billing.admin import publish_charges
from billing.models import Charge
from core.models import Notification, OwnerUnit, Resort, Unit

User = get_user_model()


class PublishChargesNotificationTests(TestCase):
    def setUp(self):
        self.resort = Resort.objects.create(name="Test Resort")
        self.unit = Unit.objects.create(resort=self.resort, unit_key="1/101")
        self.other_unit = Unit.objects.create(resort=self.resort, unit_key="2/202")

        self.manager = User.objects.create_user(
            phone="01000000099", password="x", role=User.Role.FINANCIAL_MANAGER, resort=self.resort
        )
        self.owner = User.objects.create_user(
            phone="01000000101", password="x", role=User.Role.OWNER, resort=self.resort
        )
        self.tenant = User.objects.create_user(
            phone="01000000102", password="x", role=User.Role.TENANT, resort=self.resort
        )
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        OwnerUnit.objects.create(owner=self.tenant, unit=self.unit, lease_start_date=date(2026, 6, 1))
        OwnerUnit.objects.create(owner=self.owner, unit=self.other_unit)

        patcher = mock.patch("core.tasks.send_fcm_batch_task.delay")
        self.fcm = patcher.start()
        self.addCleanup(patcher.stop)

    def _charge(self, unit=None, type=Charge.Type.ELECTRICITY, month=7, amount="100.00", status=Charge.Status.REVIEWED):
        return Charge.objects.create(
            resort=self.resort, unit=unit or self.unit, year=2026, month=month,
            type=type, amount=amount, status=status,
        )

    def _publish(self, charges):
        request = RequestFactory().post("/admin/billing/charge/")
        request.user = self.manager
        publish_charges(None, request, Charge.objects.filter(id__in=[c.id for c in charges]))

    def test_owner_gets_one_summary_per_unit_not_per_charge(self):
        charges = [
            self._charge(type=Charge.Type.ELECTRICITY, amount="100.00"),
            self._charge(type=Charge.Type.SERVICES, amount="250.50"),
            self._charge(unit=self.other_unit, amount="40.00"),
        ]
        self._publish(charges)

        notes = Notification.objects.filter(user=self.owner, type=Notification.Type.CHARGE_PUBLISHED)
        self.assertEqual(notes.count(), 2)
        by_unit = {n.data["unit_id"]: n for n in notes}
        self.assertEqual(by_unit[self.unit.id].data["count"], 2)
        self.assertIn("350.50 EGP", by_unit[self.unit.id].body)
        self.assertEqual(by_unit[self.other_unit.id].data["count"], 1)
        # owner x2 units + tenant x1 go out as ONE batch, not one push job each
        self.assertEqual(self.fcm.call_count, 1)
        self.assertEqual(len(self.fcm.call_args.args[0]), 3)

    def test_tenant_only_hears_about_charges_they_can_see(self):
        charges = [
            self._charge(type=Charge.Type.ELECTRICITY, month=7, amount="100.00"),
            self._charge(type=Charge.Type.WATER, month=3, amount="30.00"),  # before lease start
            self._charge(type=Charge.Type.SERVICES, month=7, amount="250.00"),  # not a utility
        ]
        self._publish(charges)

        notes = Notification.objects.filter(user=self.tenant)
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes[0].data["count"], 1)
        self.assertIn("100.00 EGP", notes[0].body)

    def test_tenant_with_nothing_visible_gets_no_notification(self):
        self._publish([self._charge(type=Charge.Type.SERVICES, amount="250.00")])
        self.assertFalse(Notification.objects.filter(user=self.tenant).exists())
        self.assertTrue(Notification.objects.filter(user=self.owner).exists())

    def test_already_published_charges_stay_quiet(self):
        self._publish([self._charge(status=Charge.Status.PUBLISHED)])
        self.assertFalse(Notification.objects.exists())

    def test_notification_failure_does_not_fail_the_publish(self):
        charge = self._charge()
        with mock.patch("billing.admin.notify_published_charges_task.delay", side_effect=RuntimeError("boom")):
            self._publish([charge])
        charge.refresh_from_db()
        self.assertEqual(charge.status, Charge.Status.PUBLISHED)


class PublishScaleTests(TestCase):
    """
    A resort's monthly run notifies thousands of residents at once, so the
    cost per owner has to be (near) zero queries — not a handful each.
    """

    def setUp(self):
        self.resort = Resort.objects.create(name="Big Resort")
        patcher = mock.patch("core.tasks.send_fcm_batch_task.delay")
        self.fcm = patcher.start()
        self.addCleanup(patcher.stop)

    def _owners_with_charges(self, count, start=0):
        # bulk inserts: building hundreds of residents one save() at a time
        # would dominate the test, not the thing being measured.
        keys = range(start, start + count)
        units = Unit.objects.bulk_create([Unit(resort=self.resort, unit_key=f"B{i}/1") for i in keys])
        owners = User.objects.bulk_create([
            User(phone=f"0111{i:07d}", role=User.Role.OWNER, resort=self.resort) for i in keys
        ])
        OwnerUnit.objects.bulk_create([OwnerUnit(owner=o, unit=u) for o, u in zip(owners, units)])
        charges = Charge.objects.bulk_create([
            Charge(resort=self.resort, unit=u, year=2026, month=month, type=Charge.Type.ELECTRICITY,
                   amount="100.00", status=Charge.Status.PUBLISHED)
            for u in units for month in (1, 2)
        ])
        return [c.id for c in charges]

    def _queries_for(self, charge_ids):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from billing.notifications import notify_published_charges

        with CaptureQueriesContext(connection) as ctx:
            created = notify_published_charges(charge_ids)
        return created, len(ctx)

    def test_owner_notifications_do_not_cost_queries_per_owner(self):
        small_ids = self._owners_with_charges(30)
        _, small = self._queries_for(small_ids)
        big_ids = self._owners_with_charges(300, start=30)
        created, big = self._queries_for(big_ids)

        self.assertEqual(created, 300)
        # 10x the owners, but only bulk-insert batches more — SQLite caps a
        # multi-row INSERT at ~100 rows; Postgres would stay flat.
        self.assertLessEqual(big - small, 6, f"{small} queries for 30 owners vs {big} for 300")
        self.assertLess(big, 25)

    def test_each_owner_gets_a_summary_with_their_own_total(self):
        ids = self._owners_with_charges(3)
        from billing.notifications import notify_published_charges

        notify_published_charges(ids)
        body = Notification.objects.filter(user__phone="01110000001").get().body
        self.assertEqual(body, "2 new charges were published for unit B1/1, totaling 200.00 EGP.")

    def test_inactive_residents_are_not_notified(self):
        ids = self._owners_with_charges(2)
        User.objects.filter(phone="01110000001").update(is_active=False)
        from billing.notifications import notify_published_charges

        self.assertEqual(notify_published_charges(ids), 1)
