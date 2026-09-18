"""
Dashboard callback for the Unfold Admin panel.

Security / correctness fixes applied:
  1. ALL financial queries now filter by request.tenant (the active Resort).
     Previously, totals were computed across ALL resorts — a data leak for multi-
     tenant deployments.
  2. Duplicate "Today's Collections" card for Supervisor role has been removed.
  3. Top-debtor aging is computed in Python but over a tenant-scoped queryset.
  4. SuperAdmin (who has no tenant) sees cross-resort aggregate totals as intended.
"""

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Min,
    Q,
    Sum,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def dashboard_callback(request, context):
    """
    Populate the dashboard with role-appropriate KPI cards and quick-access links.
    All financial queries are scoped to request.tenant unless the user is SuperAdmin.
    """
    from billing.models import Charge
    from collections_app.models import Payment
    from core.models import Unit
    from dateutil.relativedelta import relativedelta
    from support.models import Ticket

    user = request.user
    role = getattr(user, "role", "")
    is_super = user.is_superuser

    # Active tenant resolved by TenantMiddleware — None for SuperAdmin
    tenant = getattr(request, "tenant", None)

    # ── Tenant-scoped base filters ────────────────────────────────────────────
    # SuperAdmin intentionally sees cross-resort aggregates.
    # All other roles are strictly scoped to their resort.
    tenant_charge_filter = {} if is_super else {"resort": tenant}
    tenant_payment_filter = {} if is_super else {"resort": tenant}
    tenant_unit_filter = {} if is_super else {"resort": tenant}
    tenant_ticket_filter = {} if is_super else {"resort": tenant}

    cards: list[dict] = []
    quick_links: list[dict] = []

    # ── Pre-calculate common metrics (tenant-scoped) ──────────────────────────
    today = timezone.localdate()
    today_payments = Payment.objects.filter(
        paid_at__date=today, **tenant_payment_filter
    )
    today_count = today_payments.count()
    today_total = today_payments.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
    total_revenue = (
        Payment.objects.filter(**tenant_payment_filter)
        .aggregate(Sum("total_amount"))["total_amount__sum"]
        or 0
    )

    # ── Financial KPIs (Super, GM, FM) ───────────────────────────────────────
    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER"):
        total_original_debt = (
            Charge.objects.filter(
                status=Charge.Status.PUBLISHED, **tenant_charge_filter
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )
        total_remaining_debt = total_original_debt - total_revenue

        # Units with outstanding balance — tenant-scoped
        unpaid_units_count = (
            Unit.objects.filter(**tenant_unit_filter)
            .annotate(
                total_debt=Sum(
                    "charges__amount",
                    filter=Q(charges__status=Charge.Status.PUBLISHED),
                ),
                total_paid=Sum("charges__allocations__amount"),
            )
            .filter(total_debt__gt=F("total_paid"))
            .count()
        )

        cards.append(
            {
                "title": _("Total Revenue"),
                "metric": f"{total_revenue:,.2f} EGP",
                "footer": _("Collected from paid charges"),
                "icon": "payments",
                "color": "primary",
                "link": "/admin/collections_app/payment/",
            }
        )
        cards.append(
            {
                "title": _("Today's Collections"),
                "metric": f"{today_total:,.2f} EGP",
                "footer": f"{today_count} " + str(_("receipts today")),
                "icon": "receipt_long",
                "color": "success",
                "link": "/admin/daily-collections/",
            }
        )
        cards.append(
            {
                "title": _("Remaining Debt"),
                "metric": f"{total_remaining_debt:,.2f} EGP",
                "footer": _("Total outstanding balance"),
                "icon": "money_off",
                "color": "danger",
                "link": "/admin/core/unit/?has_balance=1",
            }
        )
        cards.append(
            {
                "title": _("Unpaid Units"),
                "metric": unpaid_units_count,
                "footer": _("Units with outstanding debt"),
                "icon": "person_off",
                "color": "warning",
                "link": "/admin/core/unit/?has_balance=1",
            }
        )

    # ── Data Entry KPIs ───────────────────────────────────────────────────────
    elif role == "DATA_ENTRY":
        total_original_debt = (
            Charge.objects.filter(
                status=Charge.Status.PUBLISHED, **tenant_charge_filter
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )
        cards.append(
            {
                "title": _("Today's Collections"),
                "metric": f"{today_total:,.2f} EGP",
                "footer": f"{today_count} " + str(_("receipts today")),
                "icon": "receipt_long",
                "color": "success",
                "link": "/admin/daily-collections/",
            }
        )
        cards.append(
            {
                "title": _("Total Original Debt"),
                "metric": f"{total_original_debt:,.2f} EGP",
                "footer": _("Total of all published charges"),
                "icon": "account_balance",
                "color": "danger",
                "link": "/admin/billing/charge/?status__exact=PUBLISHED",
            }
        )

    # ── Supervisor KPIs ───────────────────────────────────────────────────────
    # NOTE: Supervisor gets a SINGLE "Today's Collections" card here.
    # The previous implementation appended it twice (FM block + Supervisor block).
    elif role == "SUPERVISOR":
        cards.append(
            {
                "title": _("Today's Collections"),
                "metric": f"{today_total:,.2f} EGP",
                "footer": f"{today_count} " + str(_("receipts today")),
                "icon": "receipt_long",
                "color": "success",
                "link": "/admin/daily-collections/",
            }
        )

    # ── Support KPIs (Super, GM, Supervisor, Reception) ──────────────────────
    if is_super or role in ("GENERAL_MANAGER", "SUPERVISOR", "RECEPTION"):
        open_tickets = Ticket.objects.filter(
            status=Ticket.Status.OPEN, **tenant_ticket_filter
        ).count()
        cards.append(
            {
                "title": _("Open Tickets"),
                "metric": open_tickets,
                "footer": _("Support requests awaiting action"),
                "icon": "support_agent",
                "color": "danger",
                "link": "/admin/support/ticket/?status__exact=OPEN",
            }
        )

    # ── Pending Imports (Super, GM, FM, Supervisor) ───────────────────────────
    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"):
        from imports.models import ExcelUpload

        uploaded_count = ExcelUpload.objects.filter(status="UPLOADED").count()
        cards.append(
            {
                "title": _("Pending Imports"),
                "metric": uploaded_count,
                "footer": _("Excel files awaiting processing"),
                "icon": "upload_file",
                "color": "warning",
                "link": "/admin/imports/excelupload/",
            }
        )

    # ── Units KPI (Super, GM) ─────────────────────────────────────────────────
    if is_super or role == "GENERAL_MANAGER":
        total_units = Unit.objects.filter(**tenant_unit_filter).count()
        cards.append(
            {
                "title": _("Total Units"),
                "metric": total_units,
                "footer": _("Managed resort units"),
                "icon": "apartment",
                "color": "success",
                "link": "/admin/core/unit/",
            }
        )

    # ── Quick-Access Links ────────────────────────────────────────────────────

    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"):
        quick_links.append(
            {
                "title": _("Daily Collections"),
                "link": "/admin/daily-collections/",
                "icon": "monitoring",
                "icon_color": "#16a34a",
                "bg": "#f0fdf4",
                "border": "#dcfce7",
            }
        )
        quick_links.append(
            {
                "title": _("Record Payment"),
                "link": "/admin/record-payment/",
                "icon": "add_card",
                "icon_color": "#059669",
                "bg": "#ecfdf5",
                "border": "#d1fae5",
            }
        )

    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER"):
        quick_links.append(
            {
                "title": _("Billing & Charges"),
                "link": "/admin/billing/charge/",
                "icon": "request_quote",
                "icon_color": "#2563eb",
                "bg": "#eff6ff",
                "border": "#dbeafe",
            }
        )
        quick_links.append(
            {
                "title": _("Payments"),
                "link": "/admin/collections_app/payment/",
                "icon": "account_balance_wallet",
                "icon_color": "#7c3aed",
                "bg": "#f5f3ff",
                "border": "#ede9fe",
            }
        )

    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"):
        quick_links.append(
            {
                "title": _("Excel Import"),
                "link": "/admin/imports/excelupload/",
                "icon": "table_chart",
                "icon_color": "#d97706",
                "bg": "#fffbeb",
                "border": "#fef3c7",
            }
        )

    if is_super or role in ("GENERAL_MANAGER", "SUPERVISOR", "RECEPTION"):
        quick_links.append(
            {
                "title": _("Support Tickets"),
                "link": "/admin/support/ticket/",
                "icon": "confirmation_number",
                "icon_color": "#dc2626",
                "bg": "#fef2f2",
                "border": "#fecaca",
            }
        )

    if is_super or role == "GENERAL_MANAGER":
        quick_links.extend(
            [
                {
                    "title": _("Users"),
                    "link": "/admin/users/user/",
                    "icon": "group",
                    "icon_color": "#0891b2",
                    "bg": "#ecfeff",
                    "border": "#cffafe",
                },
                {
                    "title": _("Units"),
                    "link": "/admin/core/unit/",
                    "icon": "villa",
                    "icon_color": "#4f46e5",
                    "bg": "#eef2ff",
                    "border": "#e0e7ff",
                },
                {
                    "title": _("Teams"),
                    "link": "/admin/users/team/",
                    "icon": "groups",
                    "icon_color": "#0d9488",
                    "bg": "#f0fdfa",
                    "border": "#ccfbf1",
                },
            ]
        )

    if is_super:
        quick_links.extend(
            [
                {
                    "title": _("Resorts"),
                    "link": "/admin/core/resort/",
                    "icon": "holiday_village",
                    "icon_color": "#be185d",
                    "bg": "#fdf2f8",
                    "border": "#fce7f3",
                },
                {
                    "title": _("Owner Units"),
                    "link": "/admin/core/ownerunit/",
                    "icon": "real_estate_agent",
                    "icon_color": "#9333ea",
                    "bg": "#faf5ff",
                    "border": "#f3e8ff",
                },
            ]
        )

    # ── Sidebar Activity Lists (Supervisor+) — tenant-scoped ──────────────────
    recent_activity: list = []
    top_debtors: list[dict] = []

    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"):
        recent_activity = list(
            Payment.objects.filter(**tenant_payment_filter)
            .select_related("unit", "created_by")
            .order_by("-created_at")[:10]
        )

        now = timezone.now()
        top_debtors_qs = (
            Unit.objects.filter(**tenant_unit_filter)
            .annotate(
                total_debt=Sum(
                    "charges__amount",
                    filter=Q(charges__status=Charge.Status.PUBLISHED),
                ),
                total_paid=Sum(
                    "charges__allocations__amount",
                    filter=Q(charges__status=Charge.Status.PUBLISHED),
                ),
            )
            .annotate(
                balance=ExpressionWrapper(
                    F("total_debt") - F("total_paid"),
                    output_field=DecimalField(),
                ),
                oldest_charge=Min(
                    "charges__created_at",
                    filter=Q(
                        charges__status=Charge.Status.PUBLISHED,
                        charges__amount__gt=0,
                    ),
                ),
            )
            .filter(balance__gt=0)
            .order_by("-balance")[:50]
        )

        for u in top_debtors_qs:
            aging_months = 0
            if u.oldest_charge:
                diff = relativedelta(now, u.oldest_charge)
                aging_months = diff.years * 12 + diff.months

            top_debtors.append(
                {
                    "unit": u,
                    "balance": u.balance,
                    "aging_months": aging_months,
                    "unit_key": u.unit_key,
                }
            )

    context.update(
        {
            "cards": cards,
            "quick_links": quick_links,
            "recent_activity": recent_activity,
            "top_debtors": top_debtors,
            "title": _("Operations Center"),
            "subtitle": "",
        }
    )

    return context
