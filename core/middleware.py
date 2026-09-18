import logging
from django.utils.deprecation import MiddlewareMixin
from core.models import Resort, OwnerUnit

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
            if resort_id_header and resort_id_header.isdigit():
                try:
                    request.tenant = Resort.objects.get(id=int(resort_id_header), is_active=True)
                except Resort.DoesNotExist:
                    request.tenant = None
            return

        user = request.user

        # 1. Superusers only: may switch tenant context via the header (used by
        #    cross-resort tooling / support). This is the ONLY role allowed to
        #    do so.
        if getattr(user, "is_superuser", False):
            if resort_id_header and resort_id_header.isdigit():
                try:
                    request.tenant = Resort.objects.get(id=int(resort_id_header), is_active=True)
                except Resort.DoesNotExist:
                    request.tenant = getattr(user, "resort", None)
            else:
                request.tenant = getattr(user, "resort", None)
            return

        # 2. Staff (non-superuser): ALWAYS locked to their own assigned resort.
        #    The X-Resort-ID header is NEVER trusted here — a staff member's
        #    tenant must not be switchable by client-supplied input, otherwise
        #    any employee could read/write another resort's data by sending a
        #    different header value (cross-tenant IDOR).
        if user.is_staff:
            request.tenant = getattr(user, "resort", None)
            return

        # 3. Owners: Validate that owner owns a unit in the requested resort header
        if resort_id_header and resort_id_header.isdigit():
            target_resort_id = int(resort_id_header)
            owns_unit = OwnerUnit.objects.filter(
                owner=user, unit__resort_id=target_resort_id, unit__is_active=True
            ).exists()
            if owns_unit:
                try:
                    request.tenant = Resort.objects.get(id=target_resort_id, is_active=True)
                except Resort.DoesNotExist:
                    request.tenant = None
                return

        # Fallback for owner: pick the resort of their first active owned unit
        first_unit = (
            OwnerUnit.objects.filter(owner=user, unit__is_active=True)
            .select_related("unit__resort")
            .first()
        )
        if first_unit and first_unit.unit.resort.is_active:
            request.tenant = first_unit.unit.resort
        else:
            request.tenant = getattr(user, "resort", None)
