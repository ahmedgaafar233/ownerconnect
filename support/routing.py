from django.db.models import Q

from core.models import Notification
from core.notifications import notify_user
from users.models import User

from .models import Ticket

# What the Maintenance desk handles; Housekeeping is its own desk.
MAINTENANCE_TYPES = (
    Ticket.ServiceType.ELECTRICIAN,
    Ticket.ServiceType.PLUMBER,
    Ticket.ServiceType.CARPENTER,
    Ticket.ServiceType.SATELLITE,
    Ticket.ServiceType.GARDENING,
    Ticket.ServiceType.PEST_CONTROL,
)

DESK_ROLES = (User.Role.MAINTENANCE, User.Role.HOUSEKEEPING)


def department_for(service_type, category):
    """The desk role that owns a request, or None (accounts/reception/other)."""
    if service_type:
        if service_type == Ticket.ServiceType.HOUSEKEEPING:
            return User.Role.HOUSEKEEPING
        return User.Role.MAINTENANCE if service_type in MAINTENANCE_TYPES else None
    if category in (Ticket.Category.HOUSEKEEPING, Ticket.Category.CLEANING):
        return User.Role.HOUSEKEEPING
    if category == Ticket.Category.MAINTENANCE:
        return User.Role.MAINTENANCE
    return None


def _desk_q(role):
    """The same rule as department_for, as a queryset filter."""
    if role == User.Role.HOUSEKEEPING:
        return Q(service_type=Ticket.ServiceType.HOUSEKEEPING) | Q(
            service_type="", category__in=(Ticket.Category.HOUSEKEEPING, Ticket.Category.CLEANING)
        )
    return Q(service_type__in=MAINTENANCE_TYPES) | Q(service_type="", category=Ticket.Category.MAINTENANCE)


def limit_to_desk(user, queryset):
    """
    A desk user's queue is only their department's requests. Everyone else
    (Reception, supervisors, managers) sees the whole resort. This keeps the
    queues tidy — it isn't a security boundary between staff of one resort.
    """
    if user.role in DESK_ROLES:
        return queryset.filter(_desk_q(user.role))
    return queryset


def route_new_ticket(ticket):
    """
    Puts a newly raised request in front of the right desk and tells them.

    The request is not assigned to anyone — the desk dispatches it. When the
    resort has no one in that desk yet (or the request is for accounts /
    reception / something else), Reception is told instead so it never sits
    unseen.
    """
    role = department_for(ticket.service_type, ticket.category)
    recipients = []
    if role:
        recipients = list(User.objects.filter(resort_id=ticket.resort_id, role=role, is_active=True))
    if not recipients:
        recipients = list(
            User.objects.filter(resort_id=ticket.resort_id, role=User.Role.RECEPTION, is_active=True)
        )

    for staff in recipients:
        notify_user(
            staff,
            title="New Service Request",
            body=f"{ticket.subject} — unit {ticket.unit.unit_key}",
            notif_type=Notification.Type.TICKET_NEW,
            data={
                "type": "ticket_new",
                "ticket_id": ticket.id,
                "service_type": ticket.service_type,
                "unit_id": ticket.unit_id,
            },
        )
