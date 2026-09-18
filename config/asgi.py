"""
ASGI config for OwnerConnect project.

Routes HTTP traffic to Django ASGI application and WebSocket traffic to Channels
protected by JWTAuthMiddleware (for mobile clients) and AuthMiddlewareStack (for admin session fallback).
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from core.channels_middleware import JWTAuthMiddleware
import messenger.routing

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(
                messenger.routing.websocket_urlpatterns
            )
        )
    ),
})
