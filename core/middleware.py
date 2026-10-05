import logging
from django.utils.deprecation import MiddlewareMixin
from core.models import Resort
from core.tenancy import resolve_tenant

logger = logging.getLogger("core")


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that resolves the active Resort (Tenant) for each incoming request
    based on the 'X-Resort-ID' header or authenticated user's assigned resort.
    Injects request.tenant into the HttpRequest.
    """

    def process_request(self, request):
        request.tenant = None

        resort_id_header = request.headers.get("X-Resort-ID") or request.META.get("HTTP_X_RESORT_ID")
        
        if not request.user.is_authenticated:
            # Pre-login only (e.g. the resort picker). A JWT API request also
            # lands here — DRF hasn't authenticated yet — and its tenant is
            # re-resolved from the real user by TenantJWTAuthentication.
            if resort_id_header and resort_id_header.isdigit():
                try:
                    request.tenant = Resort.objects.get(id=int(resort_id_header), is_active=True)
                except Resort.DoesNotExist:
                    request.tenant = None
            return

        request.tenant = resolve_tenant(request.user, resort_id_header)
