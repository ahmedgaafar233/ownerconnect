from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import OwnerUnit, Resort, Unit
from core.testing import bearer_client
from support.models import Message, Ticket, VisitorPass

User = get_user_model()


class JWTTenantIsolationTests(TestCase):
    """
    request.tenant must come from the authenticated user, never from the raw
    X-Resort-ID header — TenantMiddleware can't know the JWT user yet.
    """

    def setUp(self):
        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B")
        self.unit_a = Unit.objects.create(resort=self.a, unit_key="1/1")
        self.unit_b = Unit.objects.create(resort=self.b, unit_key="2/2")

        self.owner_a = User.objects.create_user(phone="01000000001", password="x", role=User.Role.OWNER, resort=self.a)
        self.owner_b = User.objects.create_user(phone="01000000002", password="x", role=User.Role.OWNER, resort=self.b)
        OwnerUnit.objects.create(owner=self.owner_a, unit=self.unit_a)
        OwnerUnit.objects.create(owner=self.owner_b, unit=self.unit_b)

        now = timezone.now()
        for owner, resort, unit, name in (
            (self.owner_a, self.a, self.unit_a, "PASS-A"),
            (self.owner_b, self.b, self.unit_b, "PASS-B"),
        ):
            VisitorPass.objects.create(
                owner=owner, resort=resort, unit=unit, pass_type="VISITOR", visitor_name=name,
                valid_from=now, valid_to=now + timedelta(days=1),
            )
            Ticket.objects.create(
                owner=owner, resort=resort, unit=unit, category="MAINTENANCE",
                priority="MEDIUM", subject=f"TICKET-{name}", description="x",
            )

    def _pass_names(self, client, **headers):
        return sorted(p["visitor_name"] for p in client.get("/api/owner/passes/", **headers).json()["results"])

    def _ticket_subjects(self, client, **headers):
        return sorted(t["subject"] for t in client.get("/api/owner/tickets/", **headers).json()["results"])

    def test_staff_sees_only_their_own_resort_without_a_header(self):
        staff = User.objects.create_user(phone="01000000010", password="x", role=User.Role.RECEPTION, resort=self.a)
        client = bearer_client(staff)
        self.assertEqual(self._pass_names(client), ["PASS-A"])
        self.assertEqual(self._ticket_subjects(client), ["TICKET-PASS-A"])

    def test_staff_cannot_switch_resort_with_the_header(self):
        staff = User.objects.create_user(phone="01000000010", password="x", role=User.Role.RECEPTION, resort=self.a)
        client = bearer_client(staff)
        self.assertEqual(self._pass_names(client, HTTP_X_RESORT_ID=str(self.b.id)), ["PASS-A"])
        self.assertEqual(self._ticket_subjects(client, HTTP_X_RESORT_ID=str(self.b.id)), ["TICKET-PASS-A"])

    def test_staff_with_no_resort_sees_nothing_not_everything(self):
        staff = User.objects.create_user(phone="01000000011", password="x", role=User.Role.RECEPTION)
        client = bearer_client(staff)
        self.assertEqual(self._pass_names(client), [])
        self.assertEqual(self._ticket_subjects(client), [])

    def test_staff_cannot_read_another_resorts_ticket_messages(self):
        staff = User.objects.create_user(phone="01000000010", password="x", role=User.Role.RECEPTION, resort=self.a)
        ticket_b = Ticket.objects.get(resort=self.b)
        Message.objects.create(ticket=ticket_b, sender=self.owner_b, content="SECRET-B")
        response = bearer_client(staff).get(
            f"/api/owner/tickets/{ticket_b.id}/messages/", HTTP_X_RESORT_ID=str(self.b.id)
        )
        self.assertEqual(response.json()["results"], [])

    def test_superuser_may_switch_resort_with_the_header(self):
        admin = User.objects.create_superuser(phone="01000000099", password="x", role=User.Role.SUPERADMIN)
        client = bearer_client(admin)
        self.assertEqual(self._pass_names(client, HTTP_X_RESORT_ID=str(self.b.id)), ["PASS-B"])
        self.assertEqual(self._pass_names(client, HTTP_X_RESORT_ID=str(self.a.id)), ["PASS-A"])

    def test_superuser_without_a_resort_still_sees_everything(self):
        admin = User.objects.create_superuser(phone="01000000099", password="x", role=User.Role.SUPERADMIN)
        self.assertEqual(self._pass_names(bearer_client(admin)), ["PASS-A", "PASS-B"])

    def test_owner_header_for_a_resort_they_dont_hold_a_unit_in_is_ignored(self):
        from core.tenancy import resolve_tenant

        self.assertEqual(resolve_tenant(self.owner_a, str(self.b.id)), self.a)
        self.assertEqual(resolve_tenant(self.owner_a, str(self.a.id)), self.a)
        self.assertEqual(resolve_tenant(self.owner_a, "garbage"), self.a)


class BulkNotificationTests(TestCase):
    def setUp(self):
        self.resort = Resort.objects.create(name="Big Resort")

    def _users(self, count):
        return User.objects.bulk_create([
            User(phone=f"0122{i:07d}", role=User.Role.OWNER, resort=self.resort) for i in range(count)
        ])

    def test_pushes_are_handed_to_background_jobs_in_batches_of_500(self):
        from core.models import Notification
        from core.notifications import notify_many

        users = self._users(1100)
        with mock.patch("core.tasks.send_fcm_batch_task.delay") as delay:
            created = notify_many((u, "t", "b", Notification.Type.OTHER, {}) for u in users)

        self.assertEqual(created, 1100)
        self.assertEqual(Notification.objects.count(), 1100)
        self.assertEqual([len(call.args[0]) for call in delay.call_args_list], [500, 500, 100])

    def test_an_unqueueable_push_batch_never_loses_the_inbox_rows(self):
        from core.models import Notification
        from core.notifications import notify_many

        with mock.patch("core.tasks.send_fcm_batch_task.delay", side_effect=RuntimeError("redis down")):
            created = notify_many((u, "t", "b", Notification.Type.OTHER, {}) for u in self._users(5))
        self.assertEqual((created, Notification.objects.count()), (5, 5))

    def _run_batch_task(self, users, devices_per_user, send_each):
        from core.models import Notification
        from core.tasks import send_fcm_batch_task
        from users.models import MobileDevice

        notifications = [
            Notification.objects.create(user=u, resort=self.resort, title="t", body="b", data={"k": 1}) for u in users
        ]
        for u, n in zip(users, devices_per_user):
            for d in range(n):
                MobileDevice.objects.create(user=u, fcm_token=f"tok-{u.id}-{d}")
        with mock.patch("core.tasks._ensure_firebase"), mock.patch("firebase_admin.messaging.send_each", side_effect=send_each):
            send_fcm_batch_task([n.id for n in notifications])

    def test_the_batch_task_sends_one_message_per_device_in_calls_of_at_most_500(self):
        users = list(User.objects.filter(pk__in=[u.pk for u in self._users(3)]))
        calls = []

        def send_each(messages):
            calls.append(len(messages))
            return SimpleNamespace(success_count=len(messages), failure_count=0, responses=[SimpleNamespace(success=True)] * len(messages))

        self._run_batch_task(users, [2, 1, 0], send_each)  # 3 devices total; the third user has none
        self.assertEqual(calls, [3])

    def test_a_large_batch_is_split_to_fit_the_fcm_limit(self):
        users = list(User.objects.filter(pk__in=[u.pk for u in self._users(10)]))
        calls = []

        def send_each(messages):
            calls.append(len(messages))
            return SimpleNamespace(success_count=len(messages), failure_count=0, responses=[SimpleNamespace(success=True)] * len(messages))

        with mock.patch("core.tasks.FCM_BATCH_SIZE", 4):
            self._run_batch_task(users, [1] * 10, send_each)
        self.assertEqual(calls, [4, 4, 2])

    def test_dead_tokens_are_removed_after_a_failed_send(self):
        from users.models import MobileDevice

        users = list(User.objects.filter(pk__in=[u.pk for u in self._users(2)]))

        def send_each(messages):
            bad = SimpleNamespace(success=False, exception=SimpleNamespace(code="UNREGISTERED"))
            good = SimpleNamespace(success=True)
            return SimpleNamespace(success_count=1, failure_count=1, responses=[bad if m.token.endswith("-0") and m.token.startswith(f"tok-{users[0].id}") else good for m in messages])

        self._run_batch_task(users, [1, 1], send_each)
        self.assertEqual(list(MobileDevice.objects.values_list("user_id", flat=True)), [users[1].id])

    def test_firebases_real_dead_token_error_is_recognised(self):
        # What firebase-admin actually raises for an uninstalled app: an
        # UnregisteredError whose .code is "NOT_FOUND" — found against the
        # live service, where the old "UNREGISTERED" string never matched.
        from firebase_admin import messaging

        from core.tasks import _is_dead_token

        self.assertTrue(_is_dead_token(messaging.UnregisteredError("NotRegistered")))
        self.assertTrue(_is_dead_token(SimpleNamespace(code="NOT_FOUND")))
        self.assertTrue(_is_dead_token(SimpleNamespace(code="UNREGISTERED")))
        self.assertFalse(_is_dead_token(SimpleNamespace(code="UNAVAILABLE")))
        self.assertFalse(_is_dead_token(RuntimeError("timeout")))

    def test_pushes_ask_for_the_apps_sound_and_pop_up_channel(self):
        # Otherwise a push that arrives while the app is closed lands in
        # Firebase's quiet fallback channel: no sound, no heads-up.
        users = list(User.objects.filter(pk__in=[u.pk for u in self._users(1)]))
        sent = []

        def send_each(messages):
            sent.extend(messages)
            return SimpleNamespace(success_count=len(messages), failure_count=0, responses=[SimpleNamespace(success=True)] * len(messages))

        self._run_batch_task(users, [1], send_each)
        android = sent[0].android
        self.assertEqual(android.priority, "high")
        self.assertEqual(android.notification.channel_id, "owc_alerts")
        self.assertEqual(android.notification.sound, "owc_notify")
        self.assertEqual(sent[0].apns.payload.aps.sound, "default")
