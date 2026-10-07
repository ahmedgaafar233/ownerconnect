"""Who paid: the person named on a receipt."""
from core.models import OwnerUnit


def payer_snapshot(user):
    """Payment kwargs that record `user` as the payer — their name and role as of now."""
    if user is None:
        return {}
    return {
        "payer": user,
        "payer_name": (user.fullname or "").strip() or user.phone,
        "payer_role": user.role,
    }


def unit_residents(unit):
    """The people linked to a unit (owners first, then tenants) — who can be the payer."""
    links = OwnerUnit.objects.filter(owner__is_active=True, unit=unit).select_related("owner")
    users = [link.owner for link in links]
    users.sort(key=lambda u: (u.role != "OWNER", u.fullname or u.phone))
    return users


def default_payer(unit):
    """The unit's owner — what a receipt has always assumed — when staff don't say otherwise."""
    residents = unit_residents(unit)
    return residents[0] if residents else None
