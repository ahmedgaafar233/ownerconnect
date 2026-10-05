import base64
import shutil
import tempfile
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from announcements.admin import AnnouncementAdmin
from announcements.models import Announcement
from core.models import OwnerUnit, Resort, Unit
from core.testing import bearer_client

User = get_user_model()

# 1x1 transparent PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

LIST_URL = "/api/announcements/"


class AnnouncementFeedTests(TestCase):
    def setUp(self):
        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B")
        unit_a = Unit.objects.create(resort=self.a, unit_key="1/1")
        unit_b = Unit.objects.create(resort=self.b, unit_key="2/2")
        self.owner = User.objects.create_user(phone="01000000001", password="x", role=User.Role.OWNER, resort=self.a)
        self.tenant = User.objects.create_user(phone="01000000002", password="x", role=User.Role.TENANT, resort=self.a)
        self.owner_b = User.objects.create_user(phone="01000000003", password="x", role=User.Role.OWNER, resort=self.b)
        OwnerUnit.objects.create(owner=self.owner, unit=unit_a)
        OwnerUnit.objects.create(owner=self.tenant, unit=unit_a)
        OwnerUnit.objects.create(owner=self.owner_b, unit=unit_b)

    def _post(self, title, resort=None, **kwargs):
        kwargs.setdefault("is_published", True)
        return Announcement.objects.create(resort=resort or self.a, title=title, **kwargs)

    def _titles(self, user=None, **params):
        response = bearer_client(user or self.owner).get(LIST_URL, params)
        self.assertEqual(response.status_code, 200, response.content)
        return [a["title"] for a in response.json()["results"]]

    def test_residents_see_only_their_own_resorts_published_posts(self):
        self._post("Visible")
        self._post("Draft", is_published=False)
        self._post("Other resort", resort=self.b)
        self.assertEqual(self._titles(), ["Visible"])
        self.assertEqual(self._titles(self.owner_b), ["Other resort"])

    def test_a_tenant_can_read_the_feed_too(self):
        self._post("Visible")
        self.assertEqual(self._titles(self.tenant), ["Visible"])

    def test_the_resort_header_cannot_reach_another_resorts_feed(self):
        self._post("A post")
        self._post("B post", resort=self.b)
        response = bearer_client(self.owner).get(LIST_URL, HTTP_X_RESORT_ID=str(self.b.id))
        self.assertEqual([a["title"] for a in response.json()["results"]], ["A post"])

    def test_expired_posts_are_hidden(self):
        self._post("Live", expires_at=timezone.now() + timedelta(days=1))
        self._post("Expired", expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._titles(), ["Live"])

    def test_an_event_stays_until_the_day_after_it_happens(self):
        now = timezone.now()
        self._post("Tomorrow", kind=Announcement.Kind.EVENT, event_date=now + timedelta(days=1))
        self._post("Earlier today", kind=Announcement.Kind.EVENT, event_date=now - timedelta(hours=3))
        self._post("Last week", kind=Announcement.Kind.EVENT, event_date=now - timedelta(days=7))
        self.assertCountEqual(self._titles(), ["Tomorrow", "Earlier today"])

    def test_an_explicit_expiry_overrides_the_events_implicit_one(self):
        now = timezone.now()
        self._post(
            "Extended", kind=Announcement.Kind.EVENT,
            event_date=now - timedelta(days=7), expires_at=now + timedelta(days=1),
        )
        self.assertEqual(self._titles(), ["Extended"])

    def test_kind_filter(self):
        self._post("Flat", kind=Announcement.Kind.UNIT_FOR_SALE, price="1500000.00")
        self._post("Notice", kind=Announcement.Kind.NOTICE)
        self.assertEqual(self._titles(kind="UNIT_FOR_SALE"), ["Flat"])

    def test_newest_published_comes_first(self):
        old = self._post("Old")
        Announcement.objects.filter(pk=old.pk).update(published_at=timezone.now() - timedelta(days=2))
        self._post("New")
        self.assertEqual(self._titles(), ["New", "Old"])

    def test_staff_are_not_served_the_resident_feed(self):
        staff = User.objects.create_user(phone="01000000010", password="x", role=User.Role.RECEPTION, resort=self.a)
        self.assertEqual(bearer_client(staff).get(LIST_URL).status_code, 403)

    def test_anonymous_gets_401(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get(LIST_URL).status_code, 401)

    def test_listing_exposes_price_and_contact_but_no_internal_fields(self):
        self._post("Flat", kind=Announcement.Kind.UNIT_FOR_RENT, price="8000.00", contact_phone="0100")
        item = bearer_client(self.owner).get(LIST_URL).json()["results"][0]
        self.assertEqual(item["price"], "8000.00")
        self.assertEqual(item["contact_phone"], "0100")
        self.assertNotIn("created_by", item)
        self.assertNotIn("is_published", item)


class AnnouncementImageTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B")
        unit_a = Unit.objects.create(resort=self.a, unit_key="1/1")
        unit_b = Unit.objects.create(resort=self.b, unit_key="2/2")
        self.owner_a = User.objects.create_user(phone="01000000001", password="x", role=User.Role.OWNER, resort=self.a)
        self.owner_b = User.objects.create_user(phone="01000000003", password="x", role=User.Role.OWNER, resort=self.b)
        OwnerUnit.objects.create(owner=self.owner_a, unit=unit_a)
        OwnerUnit.objects.create(owner=self.owner_b, unit=unit_b)

        self.post = Announcement.objects.create(
            resort=self.a, title="With image", is_published=True,
            image=SimpleUploadedFile("poster.png", PNG, content_type="image/png"),
        )

    def test_list_points_at_the_authenticated_view_not_a_media_path(self):
        item = bearer_client(self.owner_a).get(LIST_URL).json()["results"][0]
        self.assertTrue(item["image_url"].endswith(f"/api/announcements/{self.post.id}/image/"))
        self.assertNotIn("/media/", item["image_url"])

    def test_a_resident_of_the_same_resort_can_download_it(self):
        response = bearer_client(self.owner_a).get(f"/api/announcements/{self.post.id}/image/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PNG)

    def test_another_resorts_resident_gets_404(self):
        self.assertEqual(bearer_client(self.owner_b).get(f"/api/announcements/{self.post.id}/image/").status_code, 404)

    def test_spoofing_the_resort_header_does_not_unlock_it(self):
        response = bearer_client(self.owner_b).get(
            f"/api/announcements/{self.post.id}/image/", HTTP_X_RESORT_ID=str(self.a.id)
        )
        self.assertEqual(response.status_code, 404)

    def test_unpublished_images_are_not_served(self):
        Announcement.objects.filter(pk=self.post.pk).update(is_published=False)
        self.assertEqual(bearer_client(self.owner_a).get(f"/api/announcements/{self.post.id}/image/").status_code, 404)

    def test_a_post_without_an_image_has_null_url_and_404s(self):
        bare = Announcement.objects.create(resort=self.a, title="Bare", is_published=True)
        self.assertEqual(bearer_client(self.owner_a).get(f"/api/announcements/{bare.id}/image/").status_code, 404)


class AnnouncementModelAndAdminTests(TestCase):
    def setUp(self):
        self.a = Resort.objects.create(name="Resort A")
        self.b = Resort.objects.create(name="Resort B")
        self.manager = User.objects.create_user(
            phone="01000000020", password="x", role=User.Role.GENERAL_MANAGER, resort=self.a
        )
        self.model_admin = AnnouncementAdmin(Announcement, admin.site)

    def _request(self, user):
        request = RequestFactory().get("/admin/announcements/announcement/")
        request.user = user
        return request

    def test_an_event_needs_a_date(self):
        with self.assertRaises(ValidationError) as ctx:
            Announcement(resort=self.a, title="Gala", kind=Announcement.Kind.EVENT).full_clean()
        self.assertIn("event_date", ctx.exception.message_dict)

    def test_published_at_is_stamped_on_first_publish_only(self):
        draft = Announcement.objects.create(resort=self.a, title="Draft")
        self.assertIsNone(draft.published_at)
        draft.is_published = True
        draft.save()
        first = draft.published_at
        self.assertIsNotNone(first)
        draft.title = "Edited"
        draft.save()
        self.assertEqual(draft.published_at, first)

    def test_staff_only_see_their_own_resorts_announcements(self):
        mine = Announcement.objects.create(resort=self.a, title="Mine")
        Announcement.objects.create(resort=self.b, title="Theirs")
        qs = self.model_admin.get_queryset(self._request(self.manager))
        self.assertEqual(list(qs), [mine])

    def test_staff_cannot_post_into_another_resort(self):
        obj = Announcement(resort=self.b, title="Sneaky")
        form = type("F", (), {"changed_data": []})()
        self.model_admin.save_model(self._request(self.manager), obj, form, change=False)
        obj.refresh_from_db()
        self.assertEqual(obj.resort, self.a)
        self.assertEqual(obj.created_by, self.manager)

    def test_residents_and_other_staff_roles_cannot_use_the_admin(self):
        owner = User.objects.create_user(phone="01000000021", password="x", role=User.Role.OWNER, resort=self.a)
        reception = User.objects.create_user(phone="01000000022", password="x", role=User.Role.RECEPTION, resort=self.a)
        self.assertFalse(self.model_admin.has_module_permission(self._request(owner)))
        self.assertFalse(self.model_admin.has_module_permission(self._request(reception)))
        self.assertTrue(self.model_admin.has_module_permission(self._request(self.manager)))
