from .models import Notification


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
