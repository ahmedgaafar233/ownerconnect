from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AnnouncementQuerySet(models.QuerySet):
    def visible(self):
        """
        What residents may see right now: published, and not past its expiry.
        An event with no explicit expiry stays up until the day after it
        happens, so stale events don't sit in the feed forever.
        """
        now = timezone.now()
        explicit_expiry = Q(expires_at__isnull=False, expires_at__gt=now)
        implicit_expiry = Q(expires_at__isnull=True) & (
            ~Q(kind=Announcement.Kind.EVENT)
            | Q(event_date__isnull=True)
            | Q(event_date__gt=now - timedelta(days=1))
        )
        return self.filter(is_published=True).filter(explicit_expiry | implicit_expiry)


class Announcement(models.Model):
    """
    A staff-authored post in a resort's Home-tab feed — replaces the physical
    TV-screen announcements. Residents only read these; there is no
    resident-authored layer yet.
    """

    class Kind(models.TextChoices):
        UNIT_FOR_SALE = "UNIT_FOR_SALE", "Unit for Sale"
        UNIT_FOR_RENT = "UNIT_FOR_RENT", "Unit for Rent"
        EVENT = "EVENT", "Event"
        NOTICE = "NOTICE", "Notice"

    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="announcements")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.NOTICE)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    # Served through an authenticated view (AnnouncementImageView), never as
    # a bare /media/ file — only resort logos are public.
    image = models.ImageField(upload_to="announcements/", blank=True, null=True)

    price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)],
        help_text="EGP. For unit listings; leave empty for \"price on request\".",
    )
    contact_phone = models.CharField(max_length=30, blank=True, default="")
    event_date = models.DateTimeField(null=True, blank=True, help_text="Required for events.")

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Hidden from the app after this time. Events with no value here stay up until the day after the event.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="announcements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["resort", "is_published", "published_at"])]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    def clean(self):
        if self.kind == self.Kind.EVENT and not self.event_date:
            raise ValidationError({"event_date": "An event needs a date."})

    def save(self, *args, **kwargs):
        if self.is_published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
