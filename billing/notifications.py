from collections import defaultdict

from django.db.models import Count, Sum

from core.models import Notification, OwnerUnit
from core.notifications import notify_many
from users.models import User

from .models import Charge

# Keeps IN (...) lists inside SQLite's bound-variable limit; Postgres doesn't care.
_CHUNK = 900


def _chunks(items, size=_CHUNK):
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start:start + size]


def notify_published_charges(charge_ids):
    """
    One notification per (resident, unit) summarising the charges that just
    went live — not one per charge. Built for a whole resort's monthly run
    (thousands of residents): owners are served from a few grouped queries
    shared by everyone, and only Tenants — whose view of a unit is limited to
    utility charges after their lease start — cost a query each, through the
    same _accessible_charges_qs the mobile charge list uses so the two can
    never disagree about what a Tenant is allowed to see.
    """
    from billing.views import _accessible_charges_qs

    charge_ids = list(charge_ids)
    if not charge_ids:
        return 0

    # unit -> (key, number of new charges, total), and unit -> its new charge ids
    unit_totals, ids_by_unit = {}, defaultdict(list)
    for chunk in _chunks(charge_ids):
        rows = (
            Charge.objects.filter(id__in=chunk, status=Charge.Status.PUBLISHED)
            .values("unit_id", "unit__unit_key")
            .annotate(count=Count("id"), total=Sum("amount"))
        )
        for row in rows:
            _key, count, total = unit_totals.get(row["unit_id"], (None, 0, 0))
            unit_totals[row["unit_id"]] = (row["unit__unit_key"], count + row["count"], total + row["total"])
        for charge_id, unit_id in Charge.objects.filter(id__in=chunk).values_list("id", "unit_id"):
            ids_by_unit[unit_id].append(charge_id)

    links = []
    for chunk in _chunks(unit_totals):
        links.extend(OwnerUnit.objects.filter(unit_id__in=chunk, owner__is_active=True).select_related("owner"))

    entries, tenant_units = [], defaultdict(list)
    for link in links:
        if link.owner.role == User.Role.TENANT:
            tenant_units[link.owner_id].append(link)
            continue
        unit_key, count, total = unit_totals[link.unit_id]
        entries.append(_entry(link.owner, link.unit_id, unit_key, count, total))

    for links_of_tenant in tenant_units.values():
        tenant = links_of_tenant[0].owner
        accessible, _unit_ids = _accessible_charges_qs(tenant)
        own_new_ids = [cid for link in links_of_tenant for cid in ids_by_unit[link.unit_id]]
        rows = (
            accessible.filter(id__in=own_new_ids)
            .values("unit_id", "unit__unit_key")
            .annotate(count=Count("id"), total=Sum("amount"))
        )
        entries.extend(_entry(tenant, r["unit_id"], r["unit__unit_key"], r["count"], r["total"]) for r in rows)

    return notify_many(entries)


def _entry(user, unit_id, unit_key, count, total):
    noun = "charge was" if count == 1 else "charges were"
    return (
        user,
        "New Charges Published",
        f"{count} new {noun} published for unit {unit_key}, totaling {total:,.2f} EGP.",
        Notification.Type.CHARGE_PUBLISHED,
        {"type": "charges_published", "unit_id": unit_id, "count": count},
    )
