from .models import OwnerUnit, Resort


def resolve_tenant(user, resort_id_header):
    """
    The Resort an authenticated user's request is scoped to — the single
    source of truth shared by TenantMiddleware (session-authenticated admin
    requests) and TenantJWTAuthentication (API requests).

    - Superusers: may switch resort via X-Resort-ID (cross-resort tooling).
    - Other staff, and the gate/beach scanner roles: ALWAYS their own
      resort; the header is never trusted, or any employee could read
      another resort's data by sending a different id (cross-tenant IDOR).
    - Owners/Tenants: the header is honoured only for a resort where they
      hold an active unit; otherwise the resort of their first active unit.
    """
    header_id = int(resort_id_header) if resort_id_header and resort_id_header.isdigit() else None

    if getattr(user, "is_superuser", False):
        if header_id:
            return Resort.objects.filter(id=header_id, is_active=True).first() or getattr(user, "resort", None)
        return getattr(user, "resort", None)

    if user.is_staff or user.role in (user.Role.SECURITY, user.Role.RECREATION):
        return getattr(user, "resort", None)

    if header_id and OwnerUnit.objects.filter(
        owner=user, unit__resort_id=header_id, unit__is_active=True
    ).exists():
        return Resort.objects.filter(id=header_id, is_active=True).first()

    first_unit = (
        OwnerUnit.objects.filter(owner=user, unit__is_active=True)
        .select_related("unit__resort")
        .first()
    )
    if first_unit and first_unit.unit.resort.is_active:
        return first_unit.unit.resort
    return getattr(user, "resort", None)


def scope_to_tenant(queryset, request, field="resort"):
    """
    Restricts a staff-facing queryset to the request's resort. Fails closed:
    with no resolved tenant only a superuser keeps the unscoped queryset —
    everyone else gets nothing rather than every resort's rows.
    """
    tenant = getattr(request, "tenant", None)
    if tenant is not None:
        return queryset.filter(**{field: tenant})
    if request.user.is_superuser:
        return queryset
    return queryset.none()
