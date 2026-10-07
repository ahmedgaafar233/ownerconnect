"""
Renting a unit out: registering a lease, who stays in it, extending or renewing
it, ending it, and who may still act on a unit once a tenant's lease is over.

The Owner registers the lease themselves — nobody approves it first; the
village's Reception and Security are notified instead. Every adult staying in
the unit is registered with their ID and gets their own gate-and-pool QR, valid
for the rental; extending or renewing the rental moves the end of those same
passes, so a QR someone already holds keeps working.
"""
import os
import re
from datetime import datetime, time, timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max, Min, Q
from django.utils import timezone

from users.models import User

from .models import Lease, LeaseAdult, LeaseDocument, MeterReading, Notification, OwnerUnit
from .notifications import notify_user

_PHONE_RE = re.compile(r"^\+\d{8,15}$")
MAX_LEASE_YEARS = 10
# A unit with no size class (so no card allowance) may still register this many adults.
MAX_ADULTS_WITHOUT_TYPE = 10


class LeaseError(Exception):
    """A rule the request broke. `field` is the form field to attach it to."""

    def __init__(self, message, field="non_field_errors"):
        super().__init__(message)
        self.field = field


def normalize_phone(raw):
    """E.164 only (what the phone sign-in itself uses): '+20 100 123 4567' -> '+201001234567'."""
    phone = re.sub(r"[\s\-()]", "", raw or "")
    if not _PHONE_RE.match(phone):
        raise LeaseError("Enter the phone number with its country code, e.g. +201001234567.", "tenant_phone")
    return phone


def has_unit_access(user, unit):
    """
    Whether `user` may still act on `unit` (open service requests, ask for
    passes). Owners always may. A Tenant may until their lease ends — after
    that they keep only the financial side (their own charges and clearance).
    """
    row = OwnerUnit.objects.filter(owner=user, unit=unit).first()
    if row is None:
        return False
    if user.role == User.Role.TENANT and row.lease_end_date and row.lease_end_date < timezone.localdate():
        return False
    return True


def current_lease(unit, today=None):
    """The lease running on `unit` today, else the next one coming up, else None."""
    today = today or timezone.localdate()
    live = Lease.objects.filter(unit=unit, cancelled_at__isnull=True, end_date__gte=today).order_by("start_date")
    return live.first()


def max_adults(unit):
    """
    How many adults a rental of this unit may register — the tenant included.
    A unit's size already fixes how many people can hold pool/beach cards (its
    card allowance); that is the natural cap here too. A unit with no size
    class set stays unrestricted up to a sane number.
    """
    allowance = unit.card_allowance
    return max(1, allowance) if allowance is not None else MAX_ADULTS_WITHOUT_TYPE


def _provision_tenant(resort, phone, name):
    """
    The TENANT account a long lease moves the unit's utilities to. Reuses the
    tenant's own account if they already have one in this village, and takes
    over an account that signed in once but was never linked to anything. An
    existing owner or staff account is never turned into a tenant.
    """
    user = User.objects.filter(phone=phone).first()
    if user is None:
        user = User.objects.create_user(phone=phone, fullname=name, role=User.Role.TENANT, resort=resort)
        return user

    if user.role == User.Role.TENANT and user.resort_id in (None, resort.id):
        changed = []
        if user.resort_id is None:
            user.resort = resort
            changed.append("resort")
        if not user.fullname:
            user.fullname = name
            changed.append("fullname")
        if changed:
            user.save(update_fields=changed)
        return user

    # A bare sign-in (default role, no village, no units) — nobody's real account yet.
    if user.role == User.Role.OWNER and user.resort_id is None and not user.owner_units.exists():
        user.role = User.Role.TENANT
        user.resort = resort
        if not user.fullname:
            user.fullname = name
        user.save()
        return user

    raise LeaseError(
        "This phone number already belongs to another account in the system (an owner, staff member, "
        "or another village's tenant). Use the tenant's own number.",
        "tenant_phone",
    )


def _village_desk_users(resort):
    return User.objects.filter(
        resort=resort,
        is_active=True,
        role__in=[User.Role.RECEPTION, User.Role.SECURITY],
    )


def _notify_village(lease, title, body, *, kind=Notification.Type.LEASE_UPDATED, event="lease_updated"):
    data = {"type": event, "lease_id": lease.id, "unit_id": lease.unit_id}
    for desk_user in _village_desk_users(lease.resort):
        notify_user(desk_user, title, body, kind, data)


def _notify_meter_reading_due(lease, moment, on):
    """
    Tells the village's Maintenance team a meter reading is due — they read
    every meter and are the source of the numbers, at a tenant's entry and exit.
    """
    users = User.objects.filter(resort=lease.resort, is_active=True, role=User.Role.MAINTENANCE)
    data = {"type": "meter_reading_due", "lease_id": lease.id, "unit_id": lease.unit_id}
    for user in users:
        notify_user(
            user,
            "Meter reading due",
            f"Read the electricity and water meters of unit {lease.unit.unit_key} at {moment} ({on:%Y-%m-%d}).",
            Notification.Type.METER_READING_DUE,
            data,
        )


def lease_meter_summary(lease):
    """
    The entry and exit readings Maintenance recorded for a rental, per meter:
    {"ELECTRICITY": {"entry": {...}|None, "exit": {...}|None}, "WATER": {...}}.
    The latest reading of each kind wins if one was taken twice.
    """
    summary = {meter: {"entry": None, "exit": None} for meter in MeterReading.Meter.values}
    readings = MeterReading.objects.filter(
        lease=lease, kind__in=(MeterReading.Kind.ENTRY, MeterReading.Kind.EXIT)
    ).order_by("read_on", "id")
    for reading in readings:
        key = "entry" if reading.kind == MeterReading.Kind.ENTRY else "exit"
        summary[reading.meter][key] = {"reading": str(reading.reading), "read_on": reading.read_on.isoformat()}
    return summary


def _validate_period(unit, start_date, end_date, *, exclude=None):
    """The date rules every new or renewed rental period must satisfy."""
    today = timezone.localdate()
    if end_date < start_date:
        raise LeaseError("The end date can't be before the start date.", "end_date")
    if end_date < today:
        raise LeaseError("The end date can't be in the past.", "end_date")
    # Months already billed to the owner can't be pushed onto a tenant after
    # the fact — a lease may start this month at the earliest.
    if start_date < today.replace(day=1):
        raise LeaseError("The start date can't be in a month that has already passed.", "start_date")
    if end_date > start_date + timedelta(days=365 * MAX_LEASE_YEARS):
        raise LeaseError(f"A lease can't be longer than {MAX_LEASE_YEARS} years.", "end_date")
    clashes = Lease.objects.filter(
        unit=unit, cancelled_at__isnull=True, start_date__lte=end_date, end_date__gte=start_date
    )
    if exclude is not None:
        clashes = clashes.exclude(pk=exclude.pk)
    if clashes.exists():
        raise LeaseError("This unit is already rented during part of that period.", "start_date")


def _require_open(lease):
    if lease.status_on(timezone.localdate()) not in (Lease.Status.ACTIVE, Lease.Status.UPCOMING):
        raise LeaseError("This rental is over. Start a new period instead.")


def _lock_unit(unit):
    # Lock the unit row so two simultaneous requests can't both pass the overlap check.
    return type(unit).objects.select_for_update().select_related("resort").get(pk=unit.pk)


# ── The QR passes ───────────────────────────────────────────────────────────


def _pass_window(start_date, end_date):
    """A rental's first minute to its last, in the resort's own time zone."""
    zone = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start_date, time.min), zone),
        timezone.make_aware(datetime.combine(end_date, time(23, 59, 59)), zone),
    )


def _issue_pass(lease, name, national_id):
    """
    A gate-and-pool QR for one adult, valid for the rental. When there's no
    tenant account (a short stay) the owner holds it — it's theirs to hand over.
    """
    from support.models import VisitorPass

    valid_from, valid_to = _pass_window(lease.start_date, lease.end_date)
    return VisitorPass.objects.create(
        owner=lease.tenant or lease.landlord,
        resort=lease.resort,
        unit=lease.unit,
        pass_type=VisitorPass.PassType.TENANT,
        visitor_name=name,
        national_id_or_passport=national_id,
        valid_from=valid_from,
        valid_to=valid_to,
        status=VisitorPass.Status.ACTIVE,
        issued_by=lease.landlord,
    )


def _sync_pass(visitor_pass):
    """
    Re-derive one pass's validity from the rentals that still use it. Extending
    or renewing a rental moves the end of the same pass, so the QR the person
    already holds keeps working; when nothing uses it any more it is cancelled.
    """
    from support.models import VisitorPass

    today = timezone.localdate()
    leases = list(
        Lease.objects.filter(
            Q(access_pass=visitor_pass) | Q(adults__access_pass=visitor_pass), cancelled_at__isnull=True
        ).distinct()
    )
    if not leases:
        visitor_pass.status = VisitorPass.Status.CANCELLED
    else:
        # Rentals not yet over decide the window; if they're all over, the latest one does.
        current = [lease for lease in leases if lease.end_date >= today] or [max(leases, key=lambda l: l.end_date)]
        visitor_pass.valid_from, visitor_pass.valid_to = _pass_window(
            min(lease.start_date for lease in current), max(lease.end_date for lease in current)
        )
        visitor_pass.status = VisitorPass.Status.ACTIVE
    visitor_pass.save(update_fields=["valid_from", "valid_to", "status"])


def passes_of(lease):
    """The tenant's pass first, then each further adult's."""
    found = [lease.access_pass] + [adult.access_pass for adult in lease.adults.select_related("access_pass")]
    return [p for p in found if p is not None]


def _resync_tenant_link(tenant_id, unit_id):
    """
    Points a tenant's OwnerUnit window at what their remaining leases on the
    unit really cover (a returning tenant can have several), or removes the
    link when none is left — only the leases that never started are dropped
    this way; a lease that ran keeps its link so the tenant can still pay.
    """
    spans = Lease.objects.filter(
        tenant_id=tenant_id, unit_id=unit_id, cancelled_at__isnull=True
    ).aggregate(first=Min("start_date"), last=Max("end_date"))
    links = OwnerUnit.objects.filter(owner_id=tenant_id, unit_id=unit_id)
    if spans["first"] is None:
        links.delete()
    else:
        links.update(lease_start_date=spans["first"], lease_end_date=spans["last"])


def _link_tenant(unit, tenant, start_date, end_date):
    link, created = OwnerUnit.objects.get_or_create(
        owner=tenant, unit=unit, defaults={"lease_start_date": start_date, "lease_end_date": end_date}
    )
    if not created:
        # A returning tenant: keep their earlier months visible (they may
        # still owe on them), and extend the window to the new end.
        link.lease_start_date = min(link.lease_start_date or start_date, start_date)
        link.lease_end_date = max(link.lease_end_date or end_date, end_date)
        link.save(update_fields=["lease_start_date", "lease_end_date"])


# ── Registering ─────────────────────────────────────────────────────────────


@transaction.atomic
def register_lease(*, landlord, unit, term, start_date, end_date, tenant_name, tenant_phone,
                   tenant_national_id, tenant_id_photo, occupants):
    """Validates and creates the lease. Raises LeaseError on a broken rule."""
    if landlord.role != User.Role.OWNER:
        raise LeaseError("Only the unit's owner can rent it out.")
    unit = _lock_unit(unit)
    if not unit.is_active or not OwnerUnit.objects.filter(owner=landlord, unit=unit).exists():
        raise LeaseError("You do not own this unit.", "unit")

    _validate_period(unit, start_date, end_date)

    tenant_name = (tenant_name or "").strip()
    tenant_national_id = (tenant_national_id or "").strip()
    if not tenant_name:
        raise LeaseError("The tenant's name is required.", "tenant_name")
    if not tenant_national_id:
        raise LeaseError("The tenant's national ID or passport number is required.", "tenant_national_id")
    if not 1 <= occupants <= 30:
        raise LeaseError("Number of occupants must be between 1 and 30.", "occupants")

    phone = normalize_phone(tenant_phone)
    if phone == landlord.phone:
        raise LeaseError("The tenant can't be the owner themselves.", "tenant_phone")

    tenant = None
    if term == Lease.Term.LONG:
        tenant = _provision_tenant(unit.resort, phone, tenant_name)
        _link_tenant(unit, tenant, start_date, end_date)

    lease = Lease.objects.create(
        resort=unit.resort,
        unit=unit,
        landlord=landlord,
        tenant=tenant,
        term=term,
        start_date=start_date,
        end_date=end_date,
        tenant_name=tenant_name,
        tenant_phone=phone,
        tenant_national_id=tenant_national_id,
        tenant_id_photo=tenant_id_photo,
        occupants=occupants,
    )
    lease.access_pass = _issue_pass(lease, tenant_name, tenant_national_id)
    lease.save(update_fields=["access_pass"])

    # Told, not asked: the village learns about the tenant the moment it's registered.
    kind = "long-term" if term == Lease.Term.LONG else "short stay"
    _notify_village(
        lease,
        "Unit rented out",
        f"Unit {unit.unit_key} is rented to {tenant_name} ({phone}), "
        f"{start_date:%Y-%m-%d} to {end_date:%Y-%m-%d} — {kind}, {occupants} occupant(s).",
        kind=Notification.Type.LEASE_REGISTERED,
        event="lease_registered",
    )
    _notify_meter_reading_due(lease, "entry", start_date)
    return lease


@transaction.atomic
def add_adult(lease, *, full_name, national_id, id_photo, relation):
    """Registers another adult staying in the unit and gives them their own QR."""
    _require_open(lease)
    full_name = (full_name or "").strip()
    national_id = (national_id or "").strip()
    if not full_name:
        raise LeaseError("The adult's name is required.", "full_name")
    if not national_id:
        raise LeaseError("The adult's national ID or passport number is required.", "national_id")
    if relation not in LeaseAdult.Relation.values:
        raise LeaseError("Choose spouse, family member or other.", "relation")

    cap = max_adults(lease.unit)
    if 1 + lease.adults.count() >= cap:
        raise LeaseError(
            f"A unit of this size has room for {cap} adult(s) in all, the tenant included.", "full_name"
        )

    adult = LeaseAdult.objects.create(
        lease=lease, full_name=full_name, national_id=national_id, id_photo=id_photo, relation=relation
    )
    adult.access_pass = _issue_pass(lease, full_name, national_id)
    adult.save(update_fields=["access_pass"])
    _notify_village(
        lease,
        "Adult added to a rental",
        f"{full_name} ({adult.get_relation_display()}) was registered for unit {lease.unit.unit_key} "
        f"with {lease.tenant_name}.",
    )
    return adult


@transaction.atomic
def remove_adult(adult):
    """An adult leaves the tenancy: their QR stops working and their ID photo is deleted."""
    lease, visitor_pass = adult.lease, adult.access_pass
    if adult.id_photo:
        adult.id_photo.delete(save=False)
    adult.delete()
    if visitor_pass is not None:
        _sync_pass(visitor_pass)
    _notify_village(
        lease, "Adult removed from a rental", f"An adult was removed from the rental of unit {lease.unit.unit_key}."
    )


@transaction.atomic
def add_document(lease, *, kind, file, label=""):
    """A paper for the village's records (marriage certificate, a passport…)."""
    if lease.cancelled_at:
        raise LeaseError("This rental was cancelled.")
    if kind not in LeaseDocument.Kind.values:
        raise LeaseError("Choose marriage certificate, passport or other.", "kind")
    document = LeaseDocument.objects.create(lease=lease, kind=kind, file=file, label=(label or "").strip()[:100])
    _notify_village(
        lease,
        "Document added to a rental",
        f"{document.get_kind_display()} added for the rental of unit {lease.unit.unit_key}.",
    )
    return document


@transaction.atomic
def remove_document(document):
    if document.file:
        document.file.delete(save=False)
    document.delete()


# ── Extending, renewing, ending ─────────────────────────────────────────────


@transaction.atomic
def extend_lease(lease, new_end):
    """
    Pushes a running (or coming) rental's end date later. It is the same
    rental, so the tenant's QR passes — and every other adult's — keep working
    through the extra time.
    """
    _require_open(lease)
    if new_end <= lease.end_date:
        raise LeaseError("The new end date must be after the current one.", "end_date")
    if new_end > lease.start_date + timedelta(days=365 * MAX_LEASE_YEARS):
        raise LeaseError(f"A lease can't be longer than {MAX_LEASE_YEARS} years.", "end_date")
    _lock_unit(lease.unit)
    clash = Lease.objects.filter(
        unit=lease.unit, cancelled_at__isnull=True, start_date__lte=new_end, end_date__gte=lease.start_date
    ).exclude(pk=lease.pk)
    if clash.exists():
        raise LeaseError("This unit is already rented during part of that period.", "end_date")

    old_end = lease.end_date
    lease.end_date = new_end
    lease.save(update_fields=["end_date"])
    if lease.tenant_id:
        _resync_tenant_link(lease.tenant_id, lease.unit_id)
    for visitor_pass in passes_of(lease):
        _sync_pass(visitor_pass)
    _notify_village(
        lease,
        "Rental extended",
        f"The rental of unit {lease.unit.unit_key} to {lease.tenant_name} now runs until {new_end:%Y-%m-%d} "
        f"(was {old_end:%Y-%m-%d}).",
    )
    return lease


def _copy_file(field_file):
    """An independent copy of a stored file — so removing it from one rental can't break the other's."""
    field_file.open("rb")
    try:
        return ContentFile(field_file.read(), name=os.path.basename(field_file.name))
    finally:
        field_file.close()


@transaction.atomic
def renew_lease(lease, *, start_date, end_date, term=None):
    """
    A new rental period for the same tenant: same people, same papers, and the
    same QR passes (their dates move to the new period), so nobody has to be
    issued anything again. A rental that's still running can only be followed
    straight on (starting the next day at the latest) — otherwise the QRs would
    be valid in the gap between the two.
    """
    if lease.cancelled_at:
        raise LeaseError("This rental was cancelled. Register a new one instead.")
    unit = _lock_unit(lease.unit)
    today = timezone.localdate()
    if lease.status_on(today) in (Lease.Status.ACTIVE, Lease.Status.UPCOMING):
        if start_date > lease.end_date + timedelta(days=1):
            raise LeaseError(
                "The new period must start right after the current one ends. To change the current one, extend it.",
                "start_date",
            )
    _validate_period(unit, start_date, end_date)

    term = term or lease.term
    if term not in Lease.Term.values:
        raise LeaseError("Choose short stay or long-term.", "term")

    tenant = None
    if term == Lease.Term.LONG:
        tenant = _provision_tenant(unit.resort, lease.tenant_phone, lease.tenant_name)
        _link_tenant(unit, tenant, start_date, end_date)

    new = Lease.objects.create(
        resort=lease.resort,
        unit=unit,
        landlord=lease.landlord,
        tenant=tenant,
        term=term,
        start_date=start_date,
        end_date=end_date,
        tenant_name=lease.tenant_name,
        tenant_phone=lease.tenant_phone,
        tenant_national_id=lease.tenant_national_id,
        tenant_id_photo=_copy_file(lease.tenant_id_photo),
        occupants=lease.occupants,
        access_pass=lease.access_pass,
    )
    for adult in lease.adults.all():
        LeaseAdult.objects.create(
            lease=new,
            full_name=adult.full_name,
            national_id=adult.national_id,
            id_photo=_copy_file(adult.id_photo),
            relation=adult.relation,
            access_pass=adult.access_pass,
        )
    for document in lease.documents.all():
        LeaseDocument.objects.create(lease=new, kind=document.kind, label=document.label, file=_copy_file(document.file))

    # Whoever holds the passes may change with the term (a short stay's are the owner's).
    holder = new.tenant or new.landlord
    for visitor_pass in passes_of(new):
        if visitor_pass.owner_id != holder.id:
            visitor_pass.owner = holder
            visitor_pass.save(update_fields=["owner"])
        _sync_pass(visitor_pass)

    _notify_village(
        new,
        "Rental renewed",
        f"The rental of unit {unit.unit_key} to {new.tenant_name} was renewed: "
        f"{start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}.",
    )
    _notify_meter_reading_due(new, "entry", start_date)
    return new


@transaction.atomic
def end_lease(lease):
    """
    The owner ends a rental early. One that hasn't started is simply cancelled;
    a running one ends yesterday, so the unit's months go back to the owner
    from this month on. Whatever the tenant still owes stays theirs to pay
    (they keep seeing it) and reverts to the owner's view per
    billing.lease_rules once the lease is over. The QRs stop with it.
    """
    today = timezone.localdate()
    status = lease.status_on(today)
    if status in (Lease.Status.ENDED, Lease.Status.CANCELLED):
        raise LeaseError("This rental has already ended.")

    yesterday = today - timedelta(days=1)
    if status == Lease.Status.UPCOMING or yesterday < lease.start_date:
        lease.cancelled_at = timezone.now()
        lease.save(update_fields=["cancelled_at"])
    else:
        lease.end_date = yesterday
        lease.save(update_fields=["end_date"])
    if lease.tenant_id:
        _resync_tenant_link(lease.tenant_id, lease.unit_id)
    for visitor_pass in passes_of(lease):
        _sync_pass(visitor_pass)

    title = "Rental ended"
    body = f"The rental of unit {lease.unit.unit_key} to {lease.tenant_name} has ended."
    _notify_village(lease, title, body, kind=Notification.Type.LEASE_ENDED, event="lease_ended")
    if status != Lease.Status.UPCOMING and lease.start_date <= lease.end_date:
        _notify_meter_reading_due(lease, "exit", lease.end_date)
    if lease.tenant_id:
        notify_user(
            lease.tenant,
            title,
            f"Your rental of unit {lease.unit.unit_key} has ended. Pay what's left on your account "
            "to get your clearance statement.",
            Notification.Type.LEASE_ENDED,
            {"type": "lease_ended", "lease_id": lease.id, "unit_id": lease.unit_id},
        )
    return lease
