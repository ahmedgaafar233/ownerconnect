"""
Dynamic sidebar navigation based on user role.
Each role sees only the sections they are authorized to access.
"""
from django.utils.translation import gettext_lazy as _


def get_navigation(request):
    """Return sidebar navigation items based on the current user's role."""
    user = request.user
    if not user.is_authenticated:
        return []

    role = getattr(user, "role", "")
    is_super = user.is_superuser

    # Role helpers
    is_gm = role == "GENERAL_MANAGER"
    is_fm = role == "FINANCIAL_MANAGER"
    is_sv = role == "SUPERVISOR"
    is_de = role == "DATA_ENTRY"
    is_rc = role == "RECEPTION"

    nav = []

    # ── Operation Center (everyone) ──
    nav.append({
        "title": _("Operation Center"),
        "separator": False,
        "items": [
            {
                "title": _("Dashboard"),
                "icon": "space_dashboard",
                "link": "/admin/",
            },
        ],
    })

    # ── Collections (Data Entry+) ──
    if is_super or is_gm or is_fm or is_sv or is_de:
        nav.append({
            "title": "التحصيلات",
            "separator": True,
            "items": [
                {
                    "title": "التحصيلات اليومية",
                    "icon": "payments",
                    "link": "/admin/daily-collections/",
                },
                {
                    "title": "تسجيل عملية تحصيل",
                    "icon": "point_of_sale",
                    "link": "/admin/record-payment/",
                },
            ],
        })

    # ── Financials (Financial Manager+) ──
    if is_super or is_gm or is_fm:
        items = [
            {
                "title": _("Billing & Charges"),
                "icon": "account_balance_wallet",
                "link": "/admin/billing/charge/",
            },
        ]
        # Excel Import visible to Supervisor and Data Entry too
        nav.append({
            "title": _("Financials"),
            "separator": True,
            "items": items,
        })

    # ── Excel Import (Supervisor+) ──
    if is_super or is_gm or is_fm or is_sv:
        nav.append({
            "title": _("Data Import"),
            "separator": True,
            "items": [
                {
                    "title": _("Excel Import"),
                    "icon": "upload_file",
                    "link": "/admin/imports/excelupload/",
                },
            ],
        })

    # ── HelpDesk (Reception+, Supervisor+) ──
    if is_super or is_gm or is_sv or is_rc:
        nav.append({
            "title": _("HelpDesk"),
            "separator": True,
            "items": [
                {
                    "title": _("Support Tickets"),
                    "icon": "support_agent",
                    "link": "/admin/support/ticket/",
                },
            ],
        })

    # ── Community (GM+) ──
    if is_super or is_gm:
        nav.append({
            "title": _("Community"),
            "separator": True,
            "items": [
                {
                    "title": _("Users & Residents"),
                    "icon": "diversity_3",
                    "link": "/admin/users/user/",
                },
                {
                    "title": _("Teams"),
                    "icon": "groups",
                    "link": "/admin/users/team/",
                },
                {
                    "title": _("Requests"),
                    "icon": "pending_actions",
                    "link": "/admin/users/teammembershiprequest/",
                },
            ],
        })

    # ── Configuration (SuperAdmin only) ──
    if is_super:
        nav.append({
            "title": _("Configuration"),
            "separator": True,
            "collapse": True,
            "items": [
                {
                    "title": _("Resorts"),
                    "icon": "villa",
                    "link": "/admin/core/resort/",
                },
                {
                    "title": _("Units"),
                    "icon": "apartment",
                    "link": "admin:core_unit_changelist",
                },
                {
                    "title": _("Owner Units"),
                    "icon": "real_estate_agent",
                    "link": "/admin/core/ownerunit/",
                },
            ],
        })
    elif is_gm or is_fm or is_sv:
        # Non-super staff can view units (read-only for most)
        nav.append({
            "title": _("Configuration"),
            "separator": True,
            "collapse": True,
            "items": [
                {
                    "title": _("Units"),
                    "icon": "apartment",
                    "link": "/admin/core/unit/",
                },
            ],
        })

    return nav
