"""
Django settings for OwnerConnect — Multi-Tenant SaaS Resort Management System.

Security hardening applied:
  - ALLOWED_HOSTS and CORS sourced from .env
  - Production security headers (HSTS, Secure cookies, XSS protection)
  - DRF throttling on auth and payment endpoints
  - Redis channel layer (replaces InMemoryChannelLayer)
  - Dedicated PAYMENT_HMAC_KEY separate from SECRET_KEY
  - DEBUG-gated SECURE_SSL_REDIRECT to allow local development
"""

import sys
from datetime import timedelta
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Environment ─────────────────────────────────────────────────────────────

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, []),
    CORS_ALLOW_CREDENTIALS=(bool, True),
)
environ.Env.read_env(str(BASE_DIR / ".env"))

# ─── Core security settings ───────────────────────────────────────────────────

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")

# PAYMENT_HMAC_KEY is the HMAC secret configured in the Paymob dashboard.
# Must be different from SECRET_KEY and never committed to version control.
PAYMENT_HMAC_KEY = env("PAYMENT_HMAC_KEY", default="")

# Paymob integration
PAYMOB_IFRAME_ID = env("PAYMOB_IFRAME_ID", default="")
PAYMOB_API_KEY = env("PAYMOB_API_KEY", default="")

ALLOWED_HOSTS: list[str] = env("ALLOWED_HOSTS")

# Dev-only Firebase-auth bypass switch (used by FirebaseAuthView so mobile/API
# testing can authenticate as any phone number without a real Firebase ID
# token, by sending "dev_test_token_<phone>"). This is DELIBERATELY separate
# from DEBUG: DEBUG is about error pages/templates and could be left on by
# mistake in a shared or staging environment, which would previously have
# silently reopened a full auth bypass. ALLOW_DEV_AUTH_BYPASS must be
# switched on explicitly and defaults to False everywhere, including when
# DEBUG=True. Set ALLOW_DEV_AUTH_BYPASS=1 in your local .env to keep using
# dev_test_token_* locally.
ALLOW_DEV_AUTH_BYPASS = env.bool("ALLOW_DEV_AUTH_BYPASS", default=False)
FIREBASE_CREDENTIALS_FILE = env("FIREBASE_CREDENTIALS_FILE", default=None)

# ─── HTTPS / Production Security Headers ─────────────────────────────────────
# These are safe to enable in production. For local HTTP development they are
# gated on DEBUG to avoid redirect/cookie issues.

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000          # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False  # Must remain False for JS CSRF reads if needed
    X_FRAME_OPTIONS = "DENY"
else:
    X_FRAME_OPTIONS = "SAMEORIGIN"  # Allows Django admin iframes locally

# ─── Application definition ───────────────────────────────────────────────────

INSTALLED_APPS = [
    "daphne",
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "core",
    "users",
    "billing",
    "imports",
    "support",
    "announcements",
    "messenger",
    "collections_app.apps.CollectionsAppConfig",
    "channels",
    "rest_framework_simplejwt.token_blacklist",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ─── Database ─────────────────────────────────────────────────────────────────

DATABASES = {
    "default": env.db("DATABASE_URL")
}

# ─── Celery (background jobs: bulk push notifications) ────────────────────────
# Publishing a month's charges notifies thousands of residents at once; that
# work runs in a worker, never inside the admin request.
CELERY_BROKER_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
# Run tasks inline instead of queueing them: always under `manage.py test`,
# and opt-in for a local dev box with no Redis (CELERY_TASK_ALWAYS_EAGER=1).
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False) or "test" in sys.argv
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TASK_IGNORE_RESULT = True
# One long job per worker slot at a time, not a prefetched backlog behind it.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Password hashing is deliberately slow; under `manage.py test` it only makes
# creating users take seconds each. Never applies outside the test runner.
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# ─── CORS ────────────────────────────────────────────────────────────────────

CORS_ALLOWED_ORIGINS: list[str] = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS: bool = env("CORS_ALLOW_CREDENTIALS")

# In development, allow localhost variants explicitly via the list in .env.
# Example .env value:
#   CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# ─── Django REST Framework ────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.authentication.TenantJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # ── Rate Limiting ──────────────────────────────────────────────────────
    # Using ScopedRateThrottle so individual views can declare throttle_scope.
    # Views that should be rate-limited must set:
    #   throttle_scope = "auth"   → applied to auth endpoints
    #   throttle_scope = "payment" → applied to payment endpoints
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Anonymous global rate (covers all unauthenticated endpoints)
        "anon": "60/minute",
        # OTP generation / activation code consumption
        "auth": "5/minute",
        # Payment session initiation
        "payment": "10/minute",
        # Gate/beach staff scanning pass QRs — busy at peak, but still capped
        # so a stolen scanner token can't be used to guess pass codes fast.
        "scan": "120/minute",
        # Registering a rental uploads an ID photo and creates an account.
        "lease": "20/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    # A stolen/leaked refresh token used to stay valid for the full 30 days
    # with no way to revoke it. Rotating on every refresh + blacklisting the
    # old token means a leaked refresh token is only usable once, and
    # logout/"sign out of this device" can now actually invalidate a token
    # instead of just discarding it client-side.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# ─── API Documentation ────────────────────────────────────────────────────────

SPECTACULAR_SETTINGS = {
    "TITLE": "OwnerConnect Resort Management API",
    "DESCRIPTION": "Multi-Tenant SaaS API for resort management and owner portal.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ─── Auth ─────────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── WebSockets / Channels ────────────────────────────────────────────────────
# IMPORTANT: Uses Redis for channel layer so WebSockets work correctly across
# multiple Daphne workers. InMemoryChannelLayer was removed — it silently drops
# messages when more than one worker is running.

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://127.0.0.1:6379/0")],
        },
    },
}

# ─── Internationalization ─────────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True

# ─── Static / Media files ─────────────────────────────────────────────────────

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Logging ──────────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "django_errors.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "billing": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "users": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "collections_app": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ─── Unfold Admin ─────────────────────────────────────────────────────────────

UNFOLD = {
    "SITE_TITLE": "Delta Sharm Resort",
    "SITE_HEADER": "Delta Sharm Resort",
    "SITE_URL": "/admin/",
    "SITE_SYMBOL": "villa",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "THEME": "light",
    "DASHBOARD_CALLBACK": "config.dashboard.dashboard_callback",
    "STYLES": [
        lambda request: "/static/core/css/sidebar_drawer.css",
    ],
    "SCRIPTS": [
        lambda request: "/static/core/js/sidebar_drawer.js",
        lambda request: "/static/core/js/sidebar_filter.js",
    ],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": "config.sidebar.get_navigation",
    },
    "COLORS": {
        "primary": {
            "50": "239 246 255",
            "100": "219 234 254",
            "200": "191 219 254",
            "300": "146 197 253",
            "400": "96 165 250",
            "500": "59 130 246",
            "600": "37 99 235",
            "700": "29 78 216",
            "800": "30 64 175",
            "900": "30 58 138",
            "950": "23 37 84",
        },
    },
}
