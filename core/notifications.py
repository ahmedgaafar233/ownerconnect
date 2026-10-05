import logging

from .models import Notification

logger = logging.getLogger(__name__)


def notify_user(user, title, body, notif_type, data=None):
    """
    Writes the in-app Notification row first (so the inbox has it even if
    FCM/Firebase isn't configured, e.g. in dev), then best-effort dispatches
    the existing push task exactly as every call site already did.
    """
    Notification.objects.create(
        user=user,
        resort=user.resort,
        type=notif_type,
        title=title,
        body=body,
        data=data or {},
    )
    try:
        from core.tasks import send_fcm_notification_task
        send_fcm_notification_task.delay(user_id=user.id, title=title, body=body, data=data)
    except Exception:
        pass


def notify_many(entries, batch_size=500):
    """
    Bulk counterpart of notify_user for sending to many residents at once
    (e.g. a published billing run). `entries` is an iterable of
    (user, title, body, notif_type, data).

    The inbox rows are written with bulk inserts, then pushes are handed to
    background jobs of `batch_size` notifications each — so the cost is a
    handful of queries and a handful of jobs, not several of each per
    recipient. Returns how many notifications were created.
    """
    notifications = [
        Notification(user=user, resort_id=user.resort_id, type=notif_type, title=title, body=body, data=data or {})
        for user, title, body, notif_type, data in entries
    ]
    if not notifications:
        return 0
    created = Notification.objects.bulk_create(notifications, batch_size=1000)

    from core.tasks import send_fcm_batch_task

    for start in range(0, len(created), batch_size):
        ids = [n.id for n in created[start:start + batch_size]]
        try:
            send_fcm_batch_task.delay(ids)
        except Exception:
            # The in-app inbox already has every row; a push that couldn't be
            # queued just means this batch isn't pushed.
            logger.warning("Could not queue an FCM batch of %d notifications", len(ids), exc_info=True)
    return len(created)


def notify_unit_counterparts(unit, acting_user, title, body, notif_type, data=None):
    """
    Notifies every other user linked to this unit via OwnerUnit (the Owner
    when a Tenant acted, the Tenant when the Owner acted) — never the
    acting user themself.
    """
    from users.models import User

    others = User.objects.filter(owner_units__unit=unit).exclude(id=acting_user.id).distinct()
    for other in others:
        notify_user(other, title, body, notif_type, data)
