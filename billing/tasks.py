from celery import shared_task

from .notifications import notify_published_charges


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def notify_published_charges_task(self, charge_ids):
    """Tells residents about a billing run in the background — see notify_published_charges."""
    try:
        return notify_published_charges(charge_ids)
    except Exception as exc:
        raise self.retry(exc=exc)
