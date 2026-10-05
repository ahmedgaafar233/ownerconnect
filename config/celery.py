import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Without this module `celery -A config worker` (docker-compose) has no app
# to load, and every task's .delay() falls back to Celery's built-in default
# app with no broker — so background pushes were silently never sent.
app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
