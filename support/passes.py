from django.utils import timezone

from core.models import Notification
from core.notifications import notify_user
from users.models import User

from .models import VisitorPass


class PassNotPending(Exception):
    """The pass was already decided (or never needed a decision)."""


def notify_security_of_request(visitor_pass):
    """Tells the resort's Security staff there's a request to confirm."""
    kind = visitor_pass.get_pass_type_display()
    for staff in User.objects.filter(
        resort_id=visitor_pass.resort_id, role=User.Role.SECURITY, is_active=True
    ):
        notify_user(
            staff,
            title="New Pass Request",
            body=f"{kind} for {visitor_pass.visitor_name} — unit {visitor_pass.unit.unit_key}",
            notif_type=Notification.Type.PASS_REQUEST,
            data={"type": "pass_request", "pass_id": visitor_pass.id, "unit_id": visitor_pass.unit_id},
        )


def _decide(visitor_pass, by, status, reason=""):
    # A conditional UPDATE, so two people deciding at once can't both win.
    decided = VisitorPass.objects.filter(pk=visitor_pass.pk, status=VisitorPass.Status.PENDING).update(
        status=status, decided_by=by, decided_at=timezone.now(), rejection_reason=reason,
    )
    if not decided:
        raise PassNotPending(visitor_pass.pk)
    visitor_pass.refresh_from_db()
    notify_pass_decision(visitor_pass)
    return visitor_pass


def approve_pass(visitor_pass, by):
    return _decide(visitor_pass, by, VisitorPass.Status.ACTIVE)


def reject_pass(visitor_pass, by, reason):
    return _decide(visitor_pass, by, VisitorPass.Status.REJECTED, reason)


def notify_pass_decision(visitor_pass):
    approved = visitor_pass.status == VisitorPass.Status.ACTIVE
    body = f"{visitor_pass.visitor_name} — unit {visitor_pass.unit.unit_key}"
    if not approved and visitor_pass.rejection_reason:
        body += f": {visitor_pass.rejection_reason}"
    notify_user(
        visitor_pass.owner,
        title="Pass Approved" if approved else "Pass Request Rejected",
        body=body,
        notif_type=Notification.Type.PASS_DECIDED,
        data={"type": "pass_decided", "pass_id": visitor_pass.id, "status": visitor_pass.status},
    )
