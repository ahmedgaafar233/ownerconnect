import urllib.parse
import logging
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from core.models import Resort, OwnerUnit

User = get_user_model()
logger = logging.getLogger("core.channels_middleware")


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Validate the SimpleJWT access token, fetch the user, and resolve active resort/tenant.
    Returns (User, Resort|None).
    """
    try:
        validated_token = AccessToken(token_string)
        user_id = validated_token.get("user_id")
        if not user_id:
            return AnonymousUser(), None

        user = User.objects.get(id=user_id, is_active=True)

        # Resolve active tenant for user
        tenant = None
        if user.is_staff or getattr(user, "is_superuser", False):
            tenant = getattr(user, "resort", None)
        else:
            first_unit = (
                OwnerUnit.objects.filter(owner=user, unit__is_active=True)
                .select_related("unit__resort")
                .first()
            )
            if first_unit and first_unit.unit.resort.is_active:
                tenant = first_unit.unit.resort
            else:
                tenant = getattr(user, "resort", None)

        return user, tenant
    except (InvalidToken, TokenError, User.DoesNotExist) as e:
        logger.warning(f"WebSocket JWT authentication failed: {e}")
        return AnonymousUser(), None
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket authentication: {e}")
        return AnonymousUser(), None


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom Channels middleware for WebSocket authentication using SimpleJWT.
    Supports token passing via:
      1. Query Parameter: ws://localhost:8000/ws/chat/1/?token=<access_token>
      2. Headers: Authorization: Bearer <access_token>
      3. Subprotocol / Sec-WebSocket-Protocol (optional)
    Attaches scope["user"] and scope["tenant"] to the WebSocket scope.
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            token = None

            # 1. Check Query String
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = urllib.parse.parse_qs(query_string)
            if "token" in query_params:
                token = query_params["token"][0]

            # 2. Check Headers if not found in query string
            if not token and "headers" in scope:
                headers = dict(scope["headers"])
                # HTTP headers in scope are byte pairs (b'header-name', b'header-value')
                auth_header = headers.get(b"authorization") or headers.get(b"sec-websocket-protocol")
                if auth_header:
                    auth_str = auth_header.decode("utf-8")
                    if auth_str.startswith("Bearer "):
                        token = auth_str.split("Bearer ")[1].strip()
                    elif auth_str.startswith("bearer "):
                        token = auth_str.split("bearer ")[1].strip()
                    else:
                        token = auth_str.strip()

            if token:
                user, tenant = await get_user_from_token(token)
                scope["user"] = user
                scope["tenant"] = tenant
            else:
                scope["user"] = AnonymousUser()
                scope["tenant"] = None

        return await super().__call__(scope, receive, send)
