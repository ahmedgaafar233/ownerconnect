"""
Which water/electricity charges belong to a tenant instead of the owner.

A LONG lease moves the unit's utility charges for the lease months (whole
calendar months, first through last — the same month granularity the tenant's
`lease_start_date` floor already uses) to the tenant's account. Maintenance,
services and annual charges never move; they stay with the owner.

While the lease is running or still to come, those charges are hidden from the
owner. Once it has ended they go back to the owner's view: whatever the tenant
didn't pay becomes the owner's to settle, so the village is never left unpaid.
"""
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from core.models import Lease

from .models import Charge

UTILITY_TYPES = (Charge.Type.ELECTRICITY, Charge.Type.WATER)


def months_between_q(start, end):
    """Charges whose (year, month) falls from start's month through end's month."""
    after_start = Q(year__gt=start.year) | Q(year=start.year, month__gte=start.month)
    before_end = Q(year__lt=end.year) | Q(year=end.year, month__lte=end.month)
    return after_start & before_end


def window_q(lease):
    """The utility charges that belong to this lease's tenant."""
    return Q(unit_id=lease.unit_id, type__in=UTILITY_TYPES) & months_between_q(lease.start_date, lease.end_date)


def transferred_q_by_unit(unit_ids, today=None):
    """
    {unit_id: Q} for the units a LONG lease currently holds (running or still
    to come) — one query for all of them, so a whole resort's publish run
    doesn't pay a query per unit. Ended and cancelled leases hold nothing.
    """
    today = today or timezone.localdate()
    leases = Lease.objects.filter(
        unit_id__in=unit_ids,
        term=Lease.Term.LONG,
        cancelled_at__isnull=True,
        end_date__gte=today,
    )
    by_unit = {}
    for lease in leases:
        by_unit[lease.unit_id] = by_unit.get(lease.unit_id, Q()) | window_q(lease)
    return by_unit


def transferred_q(unit_ids, today=None):
    """
    A Q matching the charges an Owner must NOT see right now because a LONG
    lease currently holds them, or None when none apply.
    """
    by_unit = transferred_q_by_unit(unit_ids, today)
    combined = Q()
    for q in by_unit.values():
        combined |= q
    return combined if by_unit else None


def tenant_balance(lease):
    """
    What the tenant still owes on their own lease months — the figure the
    clearance statement is gated on (cleared once it reaches zero).
    """
    charges = (
        Charge.objects.filter(status=Charge.Status.PUBLISHED)
        .filter(window_q(lease))
        .prefetch_related("allocations")
    )
    owed = Decimal("0.00")
    for charge in charges:
        paid = sum((a.amount for a in charge.allocations.all()), Decimal("0.00"))
        owed += charge.amount - paid
    return owed
