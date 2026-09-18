import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()
logger = logging.getLogger("core.tasks")


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

        # Ensure firebase_admin app is initialized
        if not firebase_admin._apps:
            cred_file = getattr(settings, "FIREBASE_CREDENTIALS_FILE", None)
            if cred_file:
                cred = firebase_admin.credentials.Certificate(cred_file)
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()

        message_data = {k: str(v) for k, v in (data or {}).items()}

        multicast_msg = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=message_data,
            tokens=tokens,
        )

        response = messaging.send_each_for_multicast(multicast_msg)
        logger.info(f"FCM multicast sent to user_id={user_id}: {response.success_count} success, {response.failure_count} failure.")

        # Clean up stale/invalid tokens
        failed_tokens = []
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                error_code = getattr(resp.exception, "code", None)
                if error_code in ["UNREGISTERED", "INVALID_ARGUMENT"]:
                    failed_tokens.append(tokens[idx])

        if failed_tokens:
            MobileDevice.objects.filter(fcm_token__in=failed_tokens).delete()
            logger.info(f"Deleted {len(failed_tokens)} stale FCM tokens for user_id={user_id}.")

    except Exception as exc:
        logger.warning(f"Error sending FCM notification for user_id={user_id}: {exc}")
        # In dev mode without Firebase credentials, gracefully log instead of failing
        if not settings.DEBUG:
            raise self.retry(exc=exc)
