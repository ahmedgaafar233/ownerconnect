import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()
logger = logging.getLogger("core.tasks")


# The Android notification channel the app creates (high importance, so the
# notification pops up on screen) and the sound it plays — a raw resource
# shipped inside the app, referenced here by name without its extension.
ANDROID_CHANNEL_ID = "owc_alerts"
ANDROID_SOUND = "owc_notify"


def _delivery_options():
    """
    How a push should alert the person: sound + heads-up on Android (via the
    channel above, which sets "pop up" behaviour) and the default sound on iOS.
    Without this a push that arrives while the app is closed uses Firebase's
    generic fallback channel — quiet, no pop-up.
    """
    from firebase_admin import messaging

    return {
        "android": messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(channel_id=ANDROID_CHANNEL_ID, sound=ANDROID_SOUND),
        ),
        "apns": messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))),
    }


def _is_dead_token(exc):
    """
    True when FCM says this device token will never work again, so it should
    be deleted. firebase-admin reports an uninstalled/expired app as
    UnregisteredError with code "NOT_FOUND" (not "UNREGISTERED") — matching
    on the code string alone, as this used to, never pruned anything.
    """
    from firebase_admin import messaging

    if isinstance(exc, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
        return True
    return getattr(exc, "code", None) in ("UNREGISTERED", "NOT_FOUND", "INVALID_ARGUMENT")


def _ensure_firebase():
    import firebase_admin

    if not firebase_admin._apps:
        cred_file = getattr(settings, "FIREBASE_CREDENTIALS_FILE", None)
        if cred_file:
            firebase_admin.initialize_app(firebase_admin.credentials.Certificate(cred_file))
        else:
            firebase_admin.initialize_app()


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def send_fcm_notification_task(self, user_id: int, title: str, body: str, data: dict | None = None):
    """
    Celery task to send FCM push notifications asynchronously to all registered devices of a user.
    """
    try:
        from users.models import MobileDevice
        import firebase_admin
        from firebase_admin import messaging

        devices = MobileDevice.objects.filter(user_id=user_id).exclude(fcm_token="")
        if not devices.exists():
            logger.info(f"No FCM devices found for user_id={user_id}")
            return

        tokens = list(devices.values_list("fcm_token", flat=True))

        _ensure_firebase()

        message_data = {k: str(v) for k, v in (data or {}).items()}

        multicast_msg = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=message_data,
            tokens=tokens,
            **_delivery_options(),
        )

        response = messaging.send_each_for_multicast(multicast_msg)
        logger.info(f"FCM multicast sent to user_id={user_id}: {response.success_count} success, {response.failure_count} failure.")

        # Clean up stale/invalid tokens
        failed_tokens = []
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                if _is_dead_token(resp.exception):
                    failed_tokens.append(tokens[idx])

        if failed_tokens:
            MobileDevice.objects.filter(fcm_token__in=failed_tokens).delete()
            logger.info(f"Deleted {len(failed_tokens)} stale FCM tokens for user_id={user_id}.")

    except Exception as exc:
        logger.warning(f"Error sending FCM notification for user_id={user_id}: {exc}")
        # In dev mode without Firebase credentials, gracefully log instead of failing
        if not settings.DEBUG:
            raise self.retry(exc=exc)


# FCM's batch API takes at most 500 messages per call.
FCM_BATCH_SIZE = 500


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_fcm_batch_task(self, notification_ids: list[int]):
    """
    Pushes a batch of already-saved in-app notifications. One job covers up to
    ~500 notifications: a single query loads their rows, a single query loads
    every recipient's devices, and the pushes go out through FCM's batch API
    (500 messages per call) — rather than one task, one query and one HTTP
    call per recipient, which is what a month-end publish to thousands of
    residents would otherwise turn into.
    """
    try:
        from core.models import Notification
        from users.models import MobileDevice
        from firebase_admin import messaging

        notifications = list(Notification.objects.filter(id__in=notification_ids))
        if not notifications:
            return

        tokens_by_user: dict[int, list[str]] = {}
        for user_id, token in MobileDevice.objects.filter(
            user_id__in={n.user_id for n in notifications}
        ).exclude(fcm_token="").values_list("user_id", "fcm_token"):
            tokens_by_user.setdefault(user_id, []).append(token)

        messages = []
        for n in notifications:
            payload = {k: str(v) for k, v in {**(n.data or {}), "notification_id": n.id}.items()}
            for token in tokens_by_user.get(n.user_id, []):
                messages.append(messaging.Message(
                    token=token,
                    notification=messaging.Notification(title=n.title, body=n.body),
                    data=payload,
                    **_delivery_options(),
                ))
        if not messages:
            logger.info(f"FCM batch: none of {len(notifications)} recipients has a registered device.")
            return

        _ensure_firebase()
        stale_tokens, sent, failed = [], 0, 0
        for start in range(0, len(messages), FCM_BATCH_SIZE):
            chunk = messages[start:start + FCM_BATCH_SIZE]
            response = messaging.send_each(chunk)
            sent += response.success_count
            failed += response.failure_count
            for message, result in zip(chunk, response.responses):
                if not result.success and _is_dead_token(result.exception):
                    stale_tokens.append(message.token)

        if stale_tokens:
            MobileDevice.objects.filter(fcm_token__in=stale_tokens).delete()
        logger.info(f"FCM batch: {sent} sent, {failed} failed, {len(stale_tokens)} stale tokens removed.")

    except Exception as exc:
        logger.warning(f"Error sending FCM batch: {exc}")
        if not settings.DEBUG:
            raise self.retry(exc=exc)
