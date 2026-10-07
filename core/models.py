from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Resort(models.Model):
    class PassIssuance(models.TextChoices):
        APPROVAL = "APPROVAL", "Security approves every pass request"
        SELF_ISSUE = "SELF_ISSUE", "Owners issue their own passes"

    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    # Villages differ: some let the owner generate the QR himself, others
    # want Security to confirm each request before it works at the gate.
    pass_issuance_mode = models.CharField(
        max_length=12, choices=PassIssuance.choices, default=PassIssuance.APPROVAL
    )
    logo = models.ImageField(upload_to="resort_logos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UnitType(models.Model):
    """
    A size class of unit (e.g. Studio, 1 Bedroom + Living Room) and how many
    beach/pool access cards a unit of that size is entitled to. Per resort,
    not global, so each resort sets its own table and nobody — owner
    included — can raise a unit's allowance from the app.
    """
    resort = models.ForeignKey(Resort, on_delete=models.CASCADE, related_name="unit_types")
    name = models.CharField(max_length=100)
    card_allowance = models.PositiveSmallIntegerField(
        help_text="Beach/pool access cards a unit of this type may hold at once."
    )

    class Meta:
        unique_together = [("resort", "name")]
        ordering = ["resort", "card_allowance", "name"]

    def __str__(self):
        return f"{self.name} ({self.card_allowance})"


class Unit(models.Model):
    resort = models.ForeignKey(Resort, on_delete=models.CASCADE, related_name="units")
    unit_key = models.CharField(max_length=100)  # مثال: 12/305
    building_no = models.CharField(max_length=50, blank=True, default="")
    unit_no = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)
    # Left null for existing units until staff assign a type — a unit with
    # no type stays unrestricted, so pilot data isn't silently locked out.
    unit_type = models.ForeignKey(
        UnitType, null=True, blank=True, on_delete=models.SET_NULL, related_name="units"
    )

    class Meta:
        unique_together = [("resort", "unit_key")]

    @property
    def card_allowance(self):
        """Max beach/pool cards this unit may hold, or None if unrestricted."""
        return self.unit_type.card_allowance if self.unit_type_id else None

    def __str__(self):
        if self.building_no or self.unit_no:
            return f"{self.resort.name} - {self.building_no}/{self.unit_no} ({self.unit_key})"
        return f"{self.resort.name} - {self.unit_key}"


class OwnerUnit(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owner_units"
    )
    unit = models.ForeignKey(
        "core.Unit",
        on_delete=models.CASCADE,
        related_name="owner_units"
    )
    # Only meaningful for a Tenant row today: a Tenant must never see/act on
    # charges dated before their own move-in. Left null for existing/Owner
    # rows so nothing is retroactively restricted until staff back-fill it.
    lease_start_date = models.DateField(null=True, blank=True)
    # The last day of a Tenant's lease. It only caps which charges they can
    # see (months after it are never theirs) and stops new requests/passes —
    # the link itself stays, so after the lease ends the tenant can still pay
    # what is left of their own period and get their clearance statement.
    lease_end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("owner", "unit")]

    def __str__(self):
        return f"{self.owner.phone} -> {self.unit.unit_key}"


class Lease(models.Model):
    """
    An Owner renting one of their units out: who the tenant is and for how
    long. The Owner registers it themselves and the village is only told —
    nobody has to approve it first.

    A LONG lease gives the tenant an account on the unit and moves the unit's
    water/electricity charges for the lease months to that account (see
    billing.lease_rules). A SHORT stay is just a record for the village — no
    account, nothing moves.
    """
    class Term(models.TextChoices):
        SHORT = "SHORT", "Short stay"
        LONG = "LONG", "Long-term (utilities move to the tenant)"

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        ACTIVE = "ACTIVE", "Active"
        ENDED = "ENDED", "Ended"
        CANCELLED = "CANCELLED", "Cancelled"

    resort = models.ForeignKey(Resort, on_delete=models.CASCADE, related_name="leases")
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="leases")
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leases_given"
    )
    # Set only for LONG leases — the account the unit's utilities move to.
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="leases_taken"
    )

    term = models.CharField(max_length=5, choices=Term.choices)
    start_date = models.DateField()
    end_date = models.DateField()

    tenant_name = models.CharField(max_length=255)
    tenant_phone = models.CharField(max_length=20)
    tenant_national_id = models.CharField(max_length=50, verbose_name="Tenant national ID / passport")
    # Private: never under a public /media/ prefix — staff read it through an
    # authenticated admin view only.
    tenant_id_photo = models.FileField(upload_to="lease_ids/")
    occupants = models.PositiveSmallIntegerField(default=1)

    # The primary tenant's gate/pool QR — a support.VisitorPass of type TENANT
    # valid for the length of the rental. Each further adult has their own
    # (see LeaseAdult). A renewal or extension reuses these same passes, so a
    # QR the tenant already holds keeps working.
    access_pass = models.ForeignKey(
        "support.VisitorPass", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        indexes = [models.Index(fields=["unit", "start_date", "end_date"])]

    def status_on(self, today):
        if self.cancelled_at:
            return self.Status.CANCELLED
        if self.start_date > today:
            return self.Status.UPCOMING
        if self.end_date < today:
            return self.Status.ENDED
        return self.Status.ACTIVE

    def __str__(self):
        return f"{self.unit.unit_key}: {self.tenant_name} ({self.start_date} → {self.end_date})"


class LeaseAdult(models.Model):
    """
    An adult staying in a rented unit besides the tenant (a spouse, a relative):
    registered with the village by their ID, and given their own gate/pool QR.
    """
    class Relation(models.TextChoices):
        SPOUSE = "SPOUSE", "Spouse"
        FAMILY = "FAMILY", "Family member"
        OTHER = "OTHER", "Other adult"

    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name="adults")
    full_name = models.CharField(max_length=255)
    national_id = models.CharField(max_length=50, verbose_name="National ID / passport")
    id_photo = models.FileField(upload_to="lease_ids/")
    relation = models.CharField(max_length=10, choices=Relation.choices, default=Relation.SPOUSE)
    access_pass = models.ForeignKey(
        "support.VisitorPass", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.full_name} ({self.get_relation_display()}) — {self.lease}"


class LeaseDocument(models.Model):
    """A paper the owner sends the village with a tenancy: marriage certificate, passports…"""
    class Kind(models.TextChoices):
        MARRIAGE_CERT = "MARRIAGE_CERT", "Marriage certificate"
        PASSPORT = "PASSPORT", "Passport"
        OTHER = "OTHER", "Other document"

    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=15, choices=Kind.choices)
    # Whose passport, say — free text, optional.
    label = models.CharField(max_length=100, blank=True, default="")
    file = models.FileField(upload_to="lease_docs/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.lease}"


class Notification(models.Model):
    class Type(models.TextChoices):
        PAYMENT_SUCCESS = "PAYMENT_SUCCESS", "Payment Successful"
        PAYMENT_DEFERRED = "PAYMENT_DEFERRED", "Payment Deferred"
        PAYMENT_PLAN_DECIDED = "PAYMENT_PLAN_DECIDED", "Payment Plan Decided"
        CHARGE_PUBLISHED = "CHARGE_PUBLISHED", "Charges Published"
        TICKET_REPLY = "TICKET_REPLY", "Support Reply"
        TICKET_NEW = "TICKET_NEW", "New Service Request"
        TICKET_STATUS = "TICKET_STATUS", "Service Request Update"
        PASS_REQUEST = "PASS_REQUEST", "New Pass Request"
        PASS_DECIDED = "PASS_DECIDED", "Pass Request Decided"
        UNIT_ACTIVITY = "UNIT_ACTIVITY", "Unit Activity"
        LEASE_REGISTERED = "LEASE_REGISTERED", "Unit Rented Out"
        LEASE_ENDED = "LEASE_ENDED", "Rental Ended"
        LEASE_UPDATED = "LEASE_UPDATED", "Rental Updated"
        METER_READING_DUE = "METER_READING_DUE", "Meter Reading Due"
        OTHER = "OTHER", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    resort = models.ForeignKey(
        Resort,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.OTHER)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    data = models.JSONField(blank=True, default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.user.phone} - {self.title}"

class MeterReading(models.Model):
    """
    A water or electricity meter reading taken by the village's Maintenance
    team. Readings at a tenant's entry and exit pin down exactly where one
    person's consumption ends and the next one's begins; they are recorded for
    reference and shown on the rental — they don't change the bills.
    """
    class Meter(models.TextChoices):
        ELECTRICITY = "ELECTRICITY", "Electricity"
        WATER = "WATER", "Water"

    class Kind(models.TextChoices):
        ENTRY = "ENTRY", "At entry"
        EXIT = "EXIT", "At exit"
        REGULAR = "REGULAR", "Regular reading"

    resort = models.ForeignKey(Resort, on_delete=models.CASCADE, related_name="meter_readings")
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="meter_readings")
    # The rental this reading belongs to — filled in automatically from the date.
    lease = models.ForeignKey(Lease, null=True, blank=True, on_delete=models.SET_NULL, related_name="meter_readings")
    meter = models.CharField(max_length=12, choices=Meter.choices)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.REGULAR)
    reading = models.DecimalField(max_digits=12, decimal_places=2)
    read_on = models.DateField(default=timezone.localdate)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="meter_readings_taken"
    )
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-read_on", "-id"]
        indexes = [models.Index(fields=["unit", "meter", "read_on"])]

    # How far from a rental's dates a reading can fall and still count as its entry/exit reading.
    LEASE_SLACK_DAYS = 3

    def save(self, *args, **kwargs):
        if self.resort_id is None and self.unit_id:
            self.resort_id = self.unit.resort_id
        if self.lease_id is None and self.unit_id:
            self.lease = self._covering_lease()
        super().save(*args, **kwargs)

    def _covering_lease(self):
        slack = timedelta(days=self.LEASE_SLACK_DAYS)
        candidates = Lease.objects.filter(
            unit_id=self.unit_id,
            cancelled_at__isnull=True,
            start_date__lte=self.read_on + slack,
            end_date__gte=self.read_on - slack,
        )
        # Prefer the rental the date actually falls inside, then the nearest.
        inside = candidates.filter(start_date__lte=self.read_on, end_date__gte=self.read_on).first()
        return inside or candidates.first()

    def __str__(self):
        return f"{self.unit.unit_key} {self.meter} {self.reading} ({self.read_on})"
