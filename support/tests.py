from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Notification, OwnerUnit, Resort, Unit, UnitType
from core.testing import bearer_client
from support.admin import PassScanAdmin, TicketAdmin, VisitorPassAdmin
from support.models import PassScan, Ticket, VisitorPass

User = get_user_model()

PASSES_URL = "/api/owner/passes/"


class CardAllowanceTests(TestCase):
    def setUp(self):
        self.resort = Resort.objects.create(name="Test Resort")
        self.studio = UnitType.objects.create(resort=self.resort, name="Studio", card_allowance=2)
        self.unit = Unit.objects.create(resort=self.resort, unit_key="1/101", unit_type=self.studio)

        self.owner = User.objects.create_user(
            phone="01000000101", password="x", role=User.Role.OWNER, resort=self.resort
        )
        self.tenant = User.objects.create_user(
            phone="01000000102", password="x", role=User.Role.TENANT, resort=self.resort
        )
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        OwnerUnit.objects.create(owner=self.tenant, unit=self.unit)

    def _post(self, user, pass_type=VisitorPass.PassType.BEACH_ACCESS, unit=None, name="Guest"):
        client = APIClient()
        client.force_authenticate(user)
        # A card spans dates; a visitor pass is a same-day visit.
        start = timezone.localtime().replace(hour=1, minute=0, second=0, microsecond=0)
        span = timedelta(hours=2) if pass_type == VisitorPass.PassType.VISITOR else timedelta(days=3)
        return client.post(PASSES_URL, {
            "unit": (unit or self.unit).id,
            "pass_type": pass_type,
            "visitor_name": name,
            "valid_from": start.isoformat(),
            "valid_to": (start + span).isoformat(),
        }, format="json")

    def test_owner_cannot_exceed_unit_allowance(self):
        self.assertEqual(self._post(self.owner, name="A").status_code, 201)
        self.assertEqual(self._post(self.owner, name="B").status_code, 201)
        response = self._post(self.owner, name="C")
        self.assertEqual(response.status_code, 400)
        self.assertIn("unit", response.json())
        self.assertEqual(VisitorPass.objects.count(), 2)

    def test_owner_and_tenant_share_one_pool(self):
        self.assertEqual(self._post(self.owner, name="A").status_code, 201)
        self.assertEqual(self._post(self.tenant, name="B").status_code, 201)
        self.assertEqual(self._post(self.owner, name="C").status_code, 400)
        self.assertEqual(self._post(self.tenant, name="D").status_code, 400)

    def test_visitor_passes_do_not_count_against_the_allowance(self):
        self._post(self.owner, name="A")
        self._post(self.owner, name="B")
        response = self._post(self.owner, pass_type=VisitorPass.PassType.VISITOR, name="Guest")
        self.assertEqual(response.status_code, 201)

    def test_cancelled_and_expired_cards_free_a_slot(self):
        self._post(self.owner, name="A")
        self._post(self.owner, name="B")
        VisitorPass.objects.filter(visitor_name="A").update(status=VisitorPass.Status.CANCELLED)
        self.assertEqual(self._post(self.owner, name="C").status_code, 201)

        VisitorPass.objects.filter(visitor_name="B").update(valid_to=timezone.now() - timedelta(hours=1))
        self.assertEqual(self._post(self.owner, name="D").status_code, 201)

    def test_unit_without_a_type_is_unrestricted(self):
        untyped = Unit.objects.create(resort=self.resort, unit_key="9/999")
        OwnerUnit.objects.create(owner=self.owner, unit=untyped)
        for i in range(5):
            self.assertEqual(self._post(self.owner, unit=untyped, name=f"G{i}").status_code, 201)

    def test_larger_unit_type_gets_a_larger_allowance(self):
        two_bed = UnitType.objects.create(resort=self.resort, name="2 Bed + Living", card_allowance=5)
        big = Unit.objects.create(resort=self.resort, unit_key="2/202", unit_type=two_bed)
        OwnerUnit.objects.create(owner=self.owner, unit=big)
        for i in range(5):
            self.assertEqual(self._post(self.owner, unit=big, name=f"G{i}").status_code, 201)
        self.assertEqual(self._post(self.owner, unit=big, name="G5").status_code, 400)

    def test_me_exposes_allowance_and_cards_used(self):
        self._post(self.owner, name="A")
        client = APIClient()
        client.force_authenticate(self.owner)
        unit = client.get("/api/me/").json()["units"][0]
        self.assertEqual(unit["card_allowance"], 2)
        self.assertEqual(unit["cards_used"], 1)

    def test_me_reports_null_allowance_for_untyped_unit(self):
        Unit.objects.filter(pk=self.unit.pk).update(unit_type=None)
        client = APIClient()
        client.force_authenticate(self.owner)
        unit = client.get("/api/me/").json()["units"][0]
        self.assertIsNone(unit["card_allowance"])


SCAN_URL = "/api/staff/passes/scan/"
REQUESTS_URL = "/api/staff/passes/requests/"
SCAN_LIST_URL = "/api/staff/passes/scans/"


class PassScanTests(TestCase):
    def setUp(self):
        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B")
        self.unit_a = Unit.objects.create(resort=self.a, unit_key="1/101")
        self.unit_b = Unit.objects.create(resort=self.b, unit_key="2/202")

        self.owner = User.objects.create_user(
            phone="01000000101", password="x", fullname="Owner One", role=User.Role.OWNER, resort=self.a
        )
        self.owner_b = User.objects.create_user(phone="01000000103", password="x", role=User.Role.OWNER, resort=self.b)
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit_a)
        OwnerUnit.objects.create(owner=self.owner_b, unit=self.unit_b)

        self.security = User.objects.create_user(phone="01000000201", password="x", role=User.Role.SECURITY, resort=self.a)
        self.recreation = User.objects.create_user(phone="01000000202", password="x", role=User.Role.RECREATION, resort=self.a)

    def _pass(self, pass_type=VisitorPass.PassType.VISITOR, owner=None, unit=None, resort=None, **kwargs):
        now = timezone.now()
        kwargs.setdefault("valid_from", now - timedelta(hours=1))
        kwargs.setdefault("valid_to", now + timedelta(days=1))
        return VisitorPass.objects.create(
            owner=owner or self.owner, unit=unit or self.unit_a, resort=resort or self.a,
            pass_type=pass_type, visitor_name=kwargs.pop("visitor_name", "Guest"),
            national_id_or_passport=kwargs.pop("national_id_or_passport", "29801011234567"), **kwargs,
        )

    def _scan(self, user, code, **extra):
        headers = extra.pop("headers", {})
        return bearer_client(user).post(SCAN_URL, {"pass_code": code, **extra}, format="json", **headers)

    # ── Security gate ────────────────────────────────────────────────────────

    def test_gate_admits_a_valid_visitor_pass_and_identifies_who_issued_it(self):
        vp = self._pass()
        response = self._scan(self.security, vp.pass_code)
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["result"], "GRANTED")
        self.assertEqual(body["pass"]["pass_type"], "VISITOR")
        self.assertEqual(body["pass"]["issued_by_role"], "OWNER")
        self.assertEqual(body["pass"]["issued_by_name"], "Owner One")
        self.assertEqual(body["pass"]["unit_key"], "1/101")
        self.assertEqual(body["pass"]["national_id_or_passport"], "29801011234567")
        self.assertEqual(body["pass"]["issued_by_phone"], "01000000101")

        scan = PassScan.objects.get()
        self.assertEqual((scan.point, scan.result, scan.scanned_by, scan.resort), ("GATE", "GRANTED", self.security, self.a))

    def test_gate_admits_a_resident_beach_card_too(self):
        vp = self._pass(pass_type=VisitorPass.PassType.BEACH_ACCESS)
        self.assertEqual(self._scan(self.security, vp.pass_code).json()["result"], "GRANTED")

    def test_unknown_code_is_denied_and_still_logged(self):
        body = self._scan(self.security, "PASS-DOESNOTEXIST").json()
        self.assertEqual((body["result"], body["reason"], body["pass"]), ("DENIED", "NOT_FOUND", None))
        scan = PassScan.objects.get()
        self.assertEqual((scan.pass_code, scan.visitor_pass), ("PASS-DOESNOTEXIST", None))

    def test_a_pass_from_another_resort_looks_unknown(self):
        other = self._pass(owner=self.owner_b, unit=self.unit_b, resort=self.b)
        body = self._scan(self.security, other.pass_code).json()
        self.assertEqual((body["result"], body["reason"], body["pass"]), ("DENIED", "NOT_FOUND", None))

    def test_the_resort_header_cannot_reach_another_resorts_passes(self):
        other = self._pass(owner=self.owner_b, unit=self.unit_b, resort=self.b)
        response = self._scan(self.security, other.pass_code, headers={"HTTP_X_RESORT_ID": str(self.b.id)})
        self.assertEqual(response.json()["reason"], "NOT_FOUND")

    def test_each_refusal_reason(self):
        now = timezone.now()
        cases = {
            "CANCELLED": self._pass(status=VisitorPass.Status.CANCELLED),
            "EXPIRED": self._pass(valid_to=now - timedelta(minutes=1)),
            "NOT_YET_VALID": self._pass(valid_from=now + timedelta(hours=2), valid_to=now + timedelta(days=1)),
        }
        expired_flag = self._pass(status=VisitorPass.Status.EXPIRED)
        for reason, vp in cases.items():
            with self.subTest(reason):
                body = self._scan(self.security, vp.pass_code).json()
                self.assertEqual((body["result"], body["reason"]), ("DENIED", reason))
                self.assertEqual(body["pass"]["visitor_name"], "Guest")
        self.assertEqual(self._scan(self.security, expired_flag.pass_code).json()["reason"], "EXPIRED")

    def test_security_cannot_log_towels(self):
        vp = self._pass()
        response = self._scan(self.security, vp.pass_code, towels_issued=2)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PassScan.objects.exists())

    # ── Recreation (beach / pool) ────────────────────────────────────────────

    def test_recreation_admits_a_beach_card_and_records_towels(self):
        vp = self._pass(pass_type=VisitorPass.PassType.BEACH_ACCESS)
        body = self._scan(self.recreation, vp.pass_code, towels_issued=2).json()
        self.assertEqual(body["result"], "GRANTED")
        scan = PassScan.objects.get()
        self.assertEqual((scan.point, scan.towels_issued), ("BEACH_POOL", 2))

    def test_recreation_refuses_a_visitor_pass(self):
        vp = self._pass(pass_type=VisitorPass.PassType.VISITOR)
        body = self._scan(self.recreation, vp.pass_code, towels_issued=2).json()
        self.assertEqual((body["result"], body["reason"]), ("DENIED", "WRONG_PASS_TYPE"))
        self.assertEqual(PassScan.objects.get().towels_issued, 0)

    def test_recreation_never_receives_the_visitors_id_or_the_residents_phone(self):
        vp = self._pass(pass_type=VisitorPass.PassType.BEACH_ACCESS)
        passed = self._scan(self.recreation, vp.pass_code).json()["pass"]
        self.assertNotIn("national_id_or_passport", passed)
        self.assertNotIn("issued_by_phone", passed)

    # ── Access control ───────────────────────────────────────────────────────

    def test_only_scanner_staff_may_scan(self):
        vp = self._pass()
        reception = User.objects.create_user(phone="01000000203", password="x", role=User.Role.RECEPTION, resort=self.a)
        for user in (self.owner, reception):
            with self.subTest(user.role):
                self.assertEqual(self._scan(user, vp.pass_code).status_code, 403)
        self.assertEqual(APIClient().post(SCAN_URL, {"pass_code": vp.pass_code}, format="json").status_code, 401)
        self.assertFalse(PassScan.objects.exists())

    def test_a_scanner_without_a_resort_is_refused(self):
        stray = User.objects.create_user(phone="01000000204", password="x", role=User.Role.SECURITY)
        self.assertEqual(self._scan(stray, "PASS-X").status_code, 403)

    def test_scanner_roles_are_not_admin_staff(self):
        self.assertFalse(self.security.is_staff)
        self.assertFalse(self.recreation.is_staff)

    def test_scan_history_is_only_the_callers_own_scans_in_their_resort(self):
        vp = self._pass()
        self._scan(self.security, vp.pass_code)
        self._scan(self.recreation, vp.pass_code)
        other_gate = User.objects.create_user(phone="01000000205", password="x", role=User.Role.SECURITY, resort=self.a)
        self._scan(other_gate, vp.pass_code)

        results = bearer_client(self.security).get(SCAN_LIST_URL).json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual((results[0]["point"], results[0]["result"], results[0]["visitor_name"]), ("GATE", "GRANTED", "Guest"))

    # ── Admin ────────────────────────────────────────────────────────────────

    def _admin_request(self, user):
        request = RequestFactory().get("/admin/support/passscan/")
        request.user = user
        return request

    def test_the_scan_log_is_read_only_and_resort_scoped(self):
        vp = self._pass()
        self._scan(self.security, vp.pass_code)
        gm_a = User.objects.create_user(phone="01000000301", password="x", role=User.Role.GENERAL_MANAGER, resort=self.a)
        gm_b = User.objects.create_user(phone="01000000302", password="x", role=User.Role.GENERAL_MANAGER, resort=self.b)
        model_admin = PassScanAdmin(PassScan, admin.site)

        self.assertEqual(model_admin.get_queryset(self._admin_request(gm_a)).count(), 1)
        self.assertEqual(model_admin.get_queryset(self._admin_request(gm_b)).count(), 0)
        request = self._admin_request(gm_a)
        self.assertTrue(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, PassScan.objects.first()))
        self.assertFalse(model_admin.has_delete_permission(request, PassScan.objects.first()))

        reception = User.objects.create_user(phone="01000000303", password="x", role=User.Role.RECEPTION, resort=self.a)
        self.assertFalse(model_admin.has_module_permission(self._admin_request(reception)))

    def test_a_superuser_can_create_scanner_staff_in_any_resort_from_the_user_admin(self):
        root = User.objects.create_superuser(phone="01000000999", password="x", role=User.Role.SUPERADMIN)
        self.client.force_login(root)
        response = self.client.post("/admin/users/user/add/", {
            "phone": "01000000555", "password1": "S3cure-pass-77", "password2": "S3cure-pass-77",
            "usable_password": "true", "role": "SECURITY", "resort": self.b.id,
            # the user admin's OwnerUnit inline needs its (empty) management form
            "owner_units-TOTAL_FORMS": 0, "owner_units-INITIAL_FORMS": 0,
            "owner_units-MIN_NUM_FORMS": 0, "owner_units-MAX_NUM_FORMS": 1000,
        })
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        created = User.objects.get(phone="01000000555")
        self.assertEqual((created.role, created.resort, created.is_staff), ("SECURITY", self.b, False))


    # ── Scanner hardware + phone: same code, same verdict ────────────────────

    def test_a_handheld_scanners_lowercase_code_with_a_trailing_newline_still_matches(self):
        vp = self._pass()
        body = self._scan(self.security, vp.pass_code.lower() + "\n").json()
        self.assertEqual(body["result"], "GRANTED")
        self.assertEqual(PassScan.objects.get().pass_code, vp.pass_code)

    def test_the_scanning_device_is_recorded(self):
        vp = self._pass()
        self._scan(self.security, vp.pass_code, device_label="Main gate 1")
        self.assertEqual(PassScan.objects.get().device_label, "Main gate 1")


class ServiceDeskTests(TestCase):
    def setUp(self):
        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B")
        self.unit = Unit.objects.create(resort=self.a, unit_key="1/101")
        self.owner = User.objects.create_user(phone="01000000101", password="x", role=User.Role.OWNER, resort=self.a)
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        self.maintenance = User.objects.create_user(phone="01000000401", password="x", role=User.Role.MAINTENANCE, resort=self.a)
        self.housekeeping = User.objects.create_user(phone="01000000402", password="x", role=User.Role.HOUSEKEEPING, resort=self.a)
        self.reception_a = User.objects.create_user(phone="01000000403", password="x", role=User.Role.RECEPTION, resort=self.a)
        self.maintenance_b = User.objects.create_user(phone="01000000404", password="x", role=User.Role.MAINTENANCE, resort=self.b)
        patcher = mock.patch("core.tasks.send_fcm_notification_task.delay")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _raise(self, user=None, **extra):
        payload = {
            "unit": self.unit.id, "category": "MAINTENANCE", "priority": "MEDIUM",
            "subject": "AC leaking", "description": "x", **extra,
        }
        return bearer_client(user or self.owner).post("/api/owner/tickets/", payload, format="json")

    def _notified(self, user):
        return Notification.objects.filter(user=user, type=Notification.Type.TICKET_NEW).count()

    # ── requests land with the right desk, unassigned ───────────────────────

    def test_a_maintenance_request_goes_to_the_maintenance_desk_only(self):
        response = self._raise(service_type="ELECTRICIAN")
        self.assertEqual(response.status_code, 201, response.content)
        ticket = Ticket.objects.get()
        self.assertEqual((ticket.assigned_to, ticket.status), (None, "OPEN"))
        self.assertEqual(
            [self._notified(u) for u in (self.maintenance, self.housekeeping, self.reception_a, self.maintenance_b)],
            [1, 0, 0, 0],
        )

    def test_a_housekeeping_request_goes_to_the_housekeeping_desk(self):
        self.assertEqual(self._raise(category="HOUSEKEEPING", service_type="HOUSEKEEPING").status_code, 201)
        self.assertEqual([self._notified(self.housekeeping), self._notified(self.maintenance)], [1, 0])

    def test_with_no_one_on_the_desk_reception_is_told_instead(self):
        User.objects.filter(role=User.Role.MAINTENANCE).delete()
        self._raise(service_type="PLUMBER")
        self.assertEqual(self._notified(self.reception_a), 1)

    def test_a_non_service_request_goes_to_reception(self):
        self._raise(category="ACCOUNTS")
        self.assertEqual([self._notified(self.reception_a), self._notified(self.maintenance)], [1, 0])

    def test_a_request_needs_no_details_just_the_kind_of_issue(self):
        # The app marks the details box "optional"; the API used to answer
        # "This field may not be blank" (found on a real phone).
        response = bearer_client(self.owner).post("/api/owner/tickets/", {
            "unit": self.unit.id, "category": "MAINTENANCE", "service_type": "ELECTRICIAN",
            "priority": "MEDIUM", "subject": "Electrician",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Ticket.objects.get().description, "")
        self.assertEqual(self._notified(self.maintenance), 1)

    def test_a_routing_failure_never_fails_the_residents_submission(self):
        with mock.patch("support.views.route_new_ticket", side_effect=RuntimeError("boom")):
            response = self._raise(service_type="PLUMBER")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_the_queue_filter_agrees_with_the_routing_rule_for_every_combination(self):
        from support.routing import department_for, limit_to_desk

        for service_type in [""] + [c for c, _ in Ticket.ServiceType.choices]:
            for category, _ in Ticket.Category.choices:
                with self.subTest(service_type=service_type, category=category):
                    ticket = Ticket.objects.create(
                        owner=self.owner, resort=self.a, unit=self.unit, category=category,
                        service_type=service_type, subject="s", description="d",
                    )
                    expected = department_for(service_type, category)
                    for desk in (self.maintenance, self.housekeeping):
                        in_queue = limit_to_desk(desk, Ticket.objects.filter(pk=ticket.pk)).exists()
                        self.assertEqual(in_queue, desk.role == expected)
                    ticket.delete()

    # ── desk screens ────────────────────────────────────────────────────────

    def test_each_desk_only_sees_its_own_departments_requests(self):
        self._raise(service_type="ELECTRICIAN", subject="Wiring")
        self._raise(category="HOUSEKEEPING", service_type="HOUSEKEEPING", subject="Deep clean")
        request = RequestFactory().get("/admin/support/ticket/")
        model_admin = TicketAdmin(Ticket, admin.site)

        def queue(user):
            request.user = user
            return sorted(t.subject for t in model_admin.get_queryset(request))

        self.assertEqual(queue(self.maintenance), ["Wiring"])
        self.assertEqual(queue(self.housekeeping), ["Deep clean"])
        self.assertEqual(queue(self.reception_a), ["Deep clean", "Wiring"])
        self.assertEqual(queue(self.maintenance_b), [])

    def test_desk_users_can_open_the_ticket_admin_but_residents_cannot(self):
        model_admin = TicketAdmin(Ticket, admin.site)
        request = RequestFactory().get("/admin/support/ticket/")
        for user, allowed in ((self.maintenance, True), (self.housekeeping, True), (self.owner, False)):
            request.user = user
            self.assertEqual(model_admin.has_module_permission(request), allowed, user.role)
        self.assertTrue(self.maintenance.is_staff)

    def test_assigning_a_technician_marks_it_assigned_and_tells_the_owner(self):
        self._raise(service_type="ELECTRICIAN")
        ticket = Ticket.objects.get()
        ticket.technician_name = "Hassan (electrician)"
        request = RequestFactory().post("/admin/support/ticket/1/change/")
        request.user = self.maintenance
        form = SimpleNamespace(initial={"status": "OPEN"})
        TicketAdmin(Ticket, admin.site).save_model(request, ticket, form, change=True)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "ASSIGNED")
        note = Notification.objects.get(user=self.owner, type=Notification.Type.TICKET_STATUS)
        self.assertEqual(note.data["status"], "ASSIGNED")

    def test_no_notification_when_the_status_did_not_change(self):
        self._raise(service_type="ELECTRICIAN")
        ticket = Ticket.objects.get()
        ticket.resolution_notes = "just a note"
        request = RequestFactory().post("/admin/support/ticket/1/change/")
        request.user = self.maintenance
        TicketAdmin(Ticket, admin.site).save_model(request, ticket, SimpleNamespace(initial={"status": "OPEN"}), change=True)
        self.assertFalse(Notification.objects.filter(user=self.owner, type=Notification.Type.TICKET_STATUS).exists())

    def test_the_desk_cannot_rewrite_what_the_owner_asked_for(self):
        self._raise(service_type="ELECTRICIAN")
        request = RequestFactory().get("/admin/support/ticket/1/change/")
        request.user = self.maintenance
        readonly = TicketAdmin(Ticket, admin.site).get_readonly_fields(request, Ticket.objects.get())
        for field in ("owner", "unit", "subject", "description", "service_type"):
            self.assertIn(field, readonly)
        self.assertNotIn("technician_name", readonly)

    def test_only_a_superuser_may_delete_a_ticket_in_the_admin(self):
        model_admin = TicketAdmin(Ticket, admin.site)
        request = RequestFactory().get("/")
        request.user = self.maintenance
        self.assertFalse(model_admin.has_delete_permission(request))

    # ── API ─────────────────────────────────────────────────────────────────

    def test_residents_can_read_but_not_change_or_delete_their_ticket(self):
        self._raise()
        ticket = Ticket.objects.get()
        client = bearer_client(self.owner)
        self.assertEqual(client.get(f"/api/owner/tickets/{ticket.id}/").status_code, 200)
        self.assertEqual(client.patch(f"/api/owner/tickets/{ticket.id}/", {"status": "CLOSED"}, format="json").status_code, 403)
        self.assertEqual(client.delete(f"/api/owner/tickets/{ticket.id}/").status_code, 403)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "OPEN")

    def test_staff_can_update_a_ticket_in_their_own_resort_only(self):
        self._raise()
        ticket = Ticket.objects.get()
        response = bearer_client(self.reception_a).patch(f"/api/owner/tickets/{ticket.id}/", {"status": "IN_PROGRESS"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(bearer_client(self.maintenance_b).patch(f"/api/owner/tickets/{ticket.id}/", {"status": "CLOSED"}, format="json").status_code, 404)

    def test_desk_users_get_their_departments_queue_from_the_api_too(self):
        self._raise(service_type="ELECTRICIAN", subject="Wiring")
        self._raise(category="HOUSEKEEPING", service_type="HOUSEKEEPING", subject="Deep clean")

        def subjects(user, **params):
            results = bearer_client(user).get("/api/owner/tickets/", params).json()["results"]
            return sorted(t["subject"] for t in results)

        self.assertEqual(subjects(self.maintenance), ["Wiring"])
        self.assertEqual(subjects(self.housekeeping), ["Deep clean"])
        self.assertEqual(subjects(self.reception_a), ["Deep clean", "Wiring"])
        self.assertEqual(subjects(self.reception_a, service_type="ELECTRICIAN"), ["Wiring"])

        Ticket.objects.filter(subject="Wiring").update(assigned_to=self.maintenance)
        self.assertEqual(subjects(self.maintenance, assigned="me"), ["Wiring"])

    def test_the_service_list_can_leave_out_pay_at_the_office_notes(self):
        self._raise(service_type="ELECTRICIAN", subject="Wiring")
        self._raise(category="ACCOUNTS", subject="Cash at the accounts office")

        def subjects(**params):
            results = bearer_client(self.owner).get("/api/owner/tickets/", params).json()["results"]
            return sorted(t["subject"] for t in results)

        self.assertEqual(subjects(), ["Cash at the accounts office", "Wiring"])
        self.assertEqual(subjects(exclude_category="ACCOUNTS"), ["Wiring"])

    def test_a_ticket_created_in_the_admin_belongs_to_its_units_resort(self):
        request = RequestFactory().post("/admin/support/ticket/add/")
        request.user = self.reception_a
        ticket = Ticket(owner=self.owner, unit=self.unit, category="MAINTENANCE", subject="x", description="x")
        TicketAdmin(Ticket, admin.site).save_model(request, ticket, form=None, change=False)
        self.assertEqual(ticket.resort, self.a)


class StaffIssuedPassTests(TestCase):
    def setUp(self):
        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B")
        studio = UnitType.objects.create(resort=self.a, name="Studio", card_allowance=1)
        self.unit = Unit.objects.create(resort=self.a, unit_key="1/101", unit_type=studio)
        self.empty_unit = Unit.objects.create(resort=self.a, unit_key="1/102")
        self.unit_b = Unit.objects.create(resort=self.b, unit_key="2/202")
        self.owner = User.objects.create_user(phone="01000000101", password="x", fullname="Owner One", role=User.Role.OWNER, resort=self.a)
        self.tenant = User.objects.create_user(phone="01000000102", password="x", role=User.Role.TENANT, resort=self.a)
        OwnerUnit.objects.create(owner=self.tenant, unit=self.unit)
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        self.reception = User.objects.create_user(phone="01000000501", password="x", role=User.Role.RECEPTION, resort=self.a)
        self.client.force_login(self.reception)

    def _issue(self, unit, **extra):
        data = {
            "unit": unit.id, "pass_type": "BEACH_ACCESS", "visitor_name": "Sara",
            "national_id_or_passport": "", "car_plate": "",
            "valid_from_0": "2026-10-01", "valid_from_1": "08:00:00",
            "valid_to_0": "2030-10-10", "valid_to_1": "20:00:00", **extra,
        }
        return self.client.post("/admin/support/visitorpass/add/", data)

    def test_reception_issues_a_pass_that_lands_in_the_units_owners_app(self):
        response = self._issue(self.unit)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        vp = VisitorPass.objects.get()
        self.assertEqual((vp.owner, vp.resort, vp.issued_by), (self.owner, self.a, self.reception))
        listed = bearer_client(self.owner).get("/api/owner/passes/").json()["results"]
        self.assertEqual([p["pass_code"] for p in listed], [vp.pass_code])

    def test_the_resort_can_exceed_the_unit_allowance_but_the_resident_then_cannot(self):
        self.assertEqual(self._issue(self.unit, visitor_name="One").status_code, 302)
        self.assertEqual(self._issue(self.unit, visitor_name="Two").status_code, 302)
        self.assertEqual(VisitorPass.objects.count(), 2)
        now = timezone.now()
        response = bearer_client(self.owner).post("/api/owner/passes/", {
            "unit": self.unit.id, "pass_type": "BEACH_ACCESS", "visitor_name": "Three",
            "valid_from": now.isoformat(), "valid_to": (now + timedelta(days=2)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_staff_cannot_issue_for_a_unit_in_another_resort(self):
        response = self._issue(self.unit_b)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(VisitorPass.objects.exists())

    def test_a_unit_with_no_linked_resident_is_refused(self):
        response = self._issue(self.empty_unit)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(VisitorPass.objects.exists())

    def test_a_pass_cannot_end_before_it_starts(self):
        response = self._issue(self.unit, valid_to_0="2026-09-01")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(VisitorPass.objects.exists())

    def test_the_admin_shows_a_qr_that_encodes_the_pass_code(self):
        import segno

        self._issue(self.unit)
        vp = VisitorPass.objects.get()
        model_admin = VisitorPassAdmin(VisitorPass, admin.site)
        expected = segno.make(vp.pass_code, error="m").svg_inline(scale=6, dark="#000", light="#fff", border=2)
        self.assertIn(expected, model_admin.qr_code(vp))
        page = self.client.get(f"/admin/support/visitorpass/{vp.id}/change/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "<svg")
        self.assertContains(page, vp.pass_code)

    def test_cancelling_from_the_admin_makes_the_gate_refuse_it(self):
        self._issue(self.unit)
        vp = VisitorPass.objects.get()
        response = self.client.post("/admin/support/visitorpass/", {
            "action": "cancel_passes", "_selected_action": [vp.id],
        })
        self.assertEqual(response.status_code, 302)
        vp.refresh_from_db()
        self.assertEqual(vp.status, "CANCELLED")

        gate = User.objects.create_user(phone="01000000601", password="x", role=User.Role.SECURITY, resort=self.a)
        body = bearer_client(gate).post("/api/staff/passes/scan/", {"pass_code": vp.pass_code}, format="json").json()
        self.assertEqual((body["result"], body["reason"]), ("DENIED", "CANCELLED"))

    def test_staff_only_see_their_own_resorts_passes(self):
        vp = VisitorPass.objects.create(
            owner=self.owner, resort=self.a, unit=self.unit, pass_type="VISITOR", visitor_name="Mine",
            valid_from=timezone.now(), valid_to=timezone.now() + timedelta(days=1),
        )
        owner_b = User.objects.create_user(phone="01000000103", password="x", role=User.Role.OWNER, resort=self.b)
        VisitorPass.objects.create(
            owner=owner_b, resort=self.b, unit=self.unit_b, pass_type="VISITOR", visitor_name="Theirs",
            valid_from=timezone.now(), valid_to=timezone.now() + timedelta(days=1),
        )
        request = RequestFactory().get("/admin/support/visitorpass/")
        request.user = self.reception
        qs = VisitorPassAdmin(VisitorPass, admin.site).get_queryset(request)
        self.assertEqual(list(qs), [vp])


class PassRequestFlowTests(TestCase):
    """Owner requests, Security confirms — unless the resort lets owners self-issue."""

    def setUp(self):
        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B", pass_issuance_mode=Resort.PassIssuance.SELF_ISSUE)
        studio = UnitType.objects.create(resort=self.a, name="Studio", card_allowance=1)
        self.unit = Unit.objects.create(resort=self.a, unit_key="1/101", unit_type=studio)
        self.unit_b = Unit.objects.create(resort=self.b, unit_key="2/202")
        self.owner = User.objects.create_user(phone="01000000101", password="x", fullname="Owner One", role=User.Role.OWNER, resort=self.a)
        self.owner_b = User.objects.create_user(phone="01000000103", password="x", role=User.Role.OWNER, resort=self.b)
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)
        OwnerUnit.objects.create(owner=self.owner_b, unit=self.unit_b)
        self.security = User.objects.create_user(phone="01000000201", password="x", role=User.Role.SECURITY, resort=self.a)
        self.security_b = User.objects.create_user(phone="01000000204", password="x", role=User.Role.SECURITY, resort=self.b)
        self.recreation = User.objects.create_user(phone="01000000202", password="x", role=User.Role.RECREATION, resort=self.a)
        patcher = mock.patch("core.tasks.send_fcm_notification_task.delay")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _request(self, user=None, unit=None, pass_type="BEACH_ACCESS", name="Sara", **times):
        start = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        payload = {
            "unit": (unit or self.unit).id, "pass_type": pass_type, "visitor_name": name,
            "valid_from": start.isoformat(),
            "valid_to": (start + timedelta(days=2)).isoformat(),
            **times,
        }
        return bearer_client(user or self.owner).post(PASSES_URL, payload, format="json")

    def _notified(self, user, notif_type):
        return Notification.objects.filter(user=user, type=notif_type).count()

    def _scan(self, user, pass_code):
        return bearer_client(user).post(SCAN_URL, {"pass_code": pass_code}, format="json").json()

    # ── creating the request ────────────────────────────────────────────────

    def test_in_an_approval_resort_a_request_is_pending_and_security_is_told(self):
        response = self._request()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["status"], "PENDING")
        self.assertEqual(self._notified(self.security, Notification.Type.PASS_REQUEST), 1)
        self.assertEqual(self._notified(self.security_b, Notification.Type.PASS_REQUEST), 0)

    def test_in_a_self_issue_resort_the_pass_is_active_at_once(self):
        now = timezone.now()
        response = self._request(
            self.owner_b, unit=self.unit_b,
            valid_from=(now - timedelta(hours=1)).isoformat(), valid_to=(now + timedelta(days=2)).isoformat(),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["status"], "ACTIVE")
        self.assertEqual(self._notified(self.security_b, Notification.Type.PASS_REQUEST), 0)
        self.assertEqual(self._scan(self.security_b, response.json()["pass_code"])["result"], "GRANTED")

    def test_a_pending_pass_does_not_work_at_the_gate(self):
        code = self._request().json()["pass_code"]
        body = self._scan(self.security, code)
        self.assertEqual((body["result"], body["reason"]), ("DENIED", "PENDING_APPROVAL"))

    def test_a_pending_card_uses_up_the_allowance(self):
        self.assertEqual(self._request().status_code, 201)
        self.assertEqual(self._request(name="Second").status_code, 400)

    # ── day visits and card date ranges ─────────────────────────────────────

    def test_a_visitor_pass_must_stay_within_one_day(self):
        start = timezone.localtime().replace(hour=20, minute=0, second=0, microsecond=0) + timedelta(days=1)
        overnight = self._request(pass_type="VISITOR", valid_from=start.isoformat(), valid_to=(start + timedelta(hours=8)).isoformat())
        self.assertEqual(overnight.status_code, 400)
        self.assertIn("valid_to", overnight.json())

        same_day = self._request(pass_type="VISITOR", valid_from=start.isoformat(), valid_to=(start + timedelta(hours=2)).isoformat())
        self.assertEqual(same_day.status_code, 201, same_day.content)

    def test_a_card_may_span_several_days(self):
        self.assertEqual(self._request(pass_type="BEACH_ACCESS").status_code, 201)

    def test_a_pass_cannot_end_before_it_starts(self):
        start = timezone.localtime() + timedelta(days=1)
        response = self._request(valid_from=start.isoformat(), valid_to=(start - timedelta(hours=1)).isoformat())
        self.assertEqual(response.status_code, 400)

    # ── Security's queue and decisions ──────────────────────────────────────

    def test_the_queue_lists_pending_requests_oldest_first_with_card_context(self):
        owner2 = User.objects.create_user(phone="01000000102", password="x", role=User.Role.OWNER, resort=self.a)
        unit2 = Unit.objects.create(resort=self.a, unit_key="1/102")
        OwnerUnit.objects.create(owner=owner2, unit=unit2)
        first = self._request(name="First").json()
        second = self._request(owner2, unit=unit2, name="Second").json()
        results = bearer_client(self.security).get(REQUESTS_URL).json()["results"]
        self.assertEqual([r["visitor_name"] for r in results], ["First", "Second"])
        self.assertEqual((results[0]["unit_card_allowance"], results[0]["unit_cards_in_use"]), (1, 1))
        self.assertEqual(results[0]["requested_by_name"], "Owner One")
        self.assertTrue(first["id"] and second["id"])

    def test_security_approves_and_the_owner_is_told_and_the_pass_works(self):
        created = self._request().json()
        response = bearer_client(self.security).post(f"/api/staff/passes/{created['id']}/approve/")
        self.assertEqual(response.status_code, 200, response.content)
        vp = VisitorPass.objects.get(pk=created["id"])
        self.assertEqual((vp.status, vp.decided_by), ("ACTIVE", self.security))
        self.assertEqual(self._notified(self.owner, Notification.Type.PASS_DECIDED), 1)
        # starts tomorrow, so the gate says "not yet" — but it is no longer pending
        self.assertEqual(self._scan(self.security, vp.pass_code)["reason"], "NOT_YET_VALID")

    def test_rejecting_needs_a_reason_and_frees_the_card(self):
        created = self._request().json()
        client = bearer_client(self.security)
        self.assertEqual(client.post(f"/api/staff/passes/{created['id']}/reject/", {}, format="json").status_code, 400)

        response = client.post(f"/api/staff/passes/{created['id']}/reject/", {"reason": "Card already issued at the desk"}, format="json")
        self.assertEqual(response.status_code, 200)
        vp = VisitorPass.objects.get(pk=created["id"])
        self.assertEqual((vp.status, vp.rejection_reason), ("REJECTED", "Card already issued at the desk"))
        note = Notification.objects.get(user=self.owner, type=Notification.Type.PASS_DECIDED)
        self.assertIn("Card already issued at the desk", note.body)
        self.assertEqual(self._scan(self.security, vp.pass_code)["reason"], "REJECTED")
        self.assertEqual(self._request(name="Retry").status_code, 201)

    def test_a_decided_request_cannot_be_decided_again(self):
        created = self._request().json()
        client = bearer_client(self.security)
        self.assertEqual(client.post(f"/api/staff/passes/{created['id']}/approve/").status_code, 200)
        self.assertEqual(client.post(f"/api/staff/passes/{created['id']}/approve/").status_code, 409)
        self.assertEqual(client.post(f"/api/staff/passes/{created['id']}/reject/", {"reason": "x"}, format="json").status_code, 409)

    def test_the_owner_sees_the_status_and_reason_in_their_app(self):
        created = self._request().json()
        bearer_client(self.security).post(f"/api/staff/passes/{created['id']}/reject/", {"reason": "No"}, format="json")
        item = bearer_client(self.owner).get(PASSES_URL).json()["results"][0]
        self.assertEqual((item["status"], item["rejection_reason"]), ("REJECTED", "No"))

    def test_only_security_may_use_the_queue_and_decide(self):
        created = self._request().json()
        reception = User.objects.create_user(phone="01000000301", password="x", role=User.Role.RECEPTION, resort=self.a)
        for user in (self.owner, self.recreation, reception):
            with self.subTest(user.role):
                client = bearer_client(user)
                self.assertEqual(client.get(REQUESTS_URL).status_code, 403)
                self.assertEqual(client.post(f"/api/staff/passes/{created['id']}/approve/").status_code, 403)
        self.assertEqual(VisitorPass.objects.get(pk=created["id"]).status, "PENDING")

    def test_security_cannot_see_or_decide_another_resorts_requests(self):
        created = self._request().json()
        other = bearer_client(self.security_b)
        self.assertEqual(other.get(REQUESTS_URL, HTTP_X_RESORT_ID=str(self.a.id)).json()["results"], [])
        self.assertEqual(other.post(f"/api/staff/passes/{created['id']}/approve/", HTTP_X_RESORT_ID=str(self.a.id)).status_code, 404)
        self.assertEqual(VisitorPass.objects.get(pk=created["id"]).status, "PENDING")

    # ── admin ───────────────────────────────────────────────────────────────

    def test_the_admin_can_approve_requests_in_bulk_and_shows_no_qr_while_pending(self):
        import segno  # noqa: F401  (the QR would need it; pending must not render one)

        reception = User.objects.create_user(phone="01000000302", password="x", role=User.Role.RECEPTION, resort=self.a)
        created = self._request().json()
        self.client.force_login(reception)
        page = self.client.get(f"/admin/support/visitorpass/{created['id']}/change/")
        self.assertContains(page, "No QR")
        self.assertNotContains(page, "<svg class=\"segno\"")

        response = self.client.post("/admin/support/visitorpass/", {"action": "approve_pass_requests", "_selected_action": [created["id"]]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VisitorPass.objects.get(pk=created["id"]).status, "ACTIVE")
        self.assertEqual(self._notified(self.owner, Notification.Type.PASS_DECIDED), 1)


class PassDatesTests(TestCase):
    """Dates are resort-calendar days, so the phone's time zone can't break them."""

    def setUp(self):
        self.resort = Resort.objects.create(name="Resort", pass_issuance_mode=Resort.PassIssuance.SELF_ISSUE)
        self.unit = Unit.objects.create(resort=self.resort, unit_key="1/101")
        self.owner = User.objects.create_user(phone="01000000101", password="x", role=User.Role.OWNER, resort=self.resort)
        OwnerUnit.objects.create(owner=self.owner, unit=self.unit)

    def _post(self, **fields):
        payload = {"unit": self.unit.id, "pass_type": "VISITOR", "visitor_name": "Guest", **fields}
        return bearer_client(self.owner).post(PASSES_URL, payload, format="json")

    def _tomorrow(self, days=1):
        return (timezone.localdate() + timedelta(days=days)).isoformat()

    def test_a_visit_date_becomes_that_whole_day_in_the_resorts_time_zone(self):
        response = self._post(start_date=self._tomorrow())
        self.assertEqual(response.status_code, 201, response.content)
        vp = VisitorPass.objects.get()
        local_from, local_to = timezone.localtime(vp.valid_from), timezone.localtime(vp.valid_to)
        self.assertEqual(str(local_from.date()), self._tomorrow())
        self.assertEqual((local_from.hour, local_from.minute), (0, 0))
        self.assertEqual((local_to.date(), local_to.hour, local_to.minute), (local_from.date(), 23, 59))

    def test_a_visit_cannot_span_several_dates(self):
        response = self._post(start_date=self._tomorrow(1), end_date=self._tomorrow(2))
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid_to", response.json())

    def test_a_card_takes_a_date_range(self):
        response = self._post(pass_type="BEACH_ACCESS", start_date=self._tomorrow(1), end_date=self._tomorrow(5))
        self.assertEqual(response.status_code, 201, response.content)
        vp = VisitorPass.objects.get()
        self.assertEqual((vp.valid_to - vp.valid_from).days, 4)

    def test_a_date_that_has_passed_is_refused(self):
        response = self._post(start_date=self._tomorrow(-3))
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date", response.json())

    def test_either_dates_or_instants_are_required(self):
        self.assertEqual(self._post().status_code, 400)

    def test_exact_instants_still_work(self):
        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        response = self._post(valid_from=now.isoformat(), valid_to=(now + timedelta(hours=3)).isoformat())
        self.assertEqual(response.status_code, 201, response.content)
