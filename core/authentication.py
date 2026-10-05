from rest_framework_simplejwt.authentication import JWTAuthentication

from .tenancy import resolve_tenant


class TenantJWTAuthentication(JWTAuthentication):
    """
    JWTAuthentication that also resolves request.tenant for the user it just
    authenticated.

    TenantMiddleware runs before DRF authenticates, so on a JWT request it
    only ever sees an anonymous user — and its anonymous branch takes the raw
    client-sent X-Resort-ID header at face value. Left alone, that made
    request.tenant client-controlled for every API caller, including staff,
    defeating the "staff are locked to their own resort" rule. Resolving it
    here, once the user is known, applies the real rules.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            tenant = resolve_tenant(user, request.headers.get("X-Resort-ID"))
            request.tenant = tenant
            request._request.tenant = tenant
        return result
