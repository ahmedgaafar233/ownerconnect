from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from django.utils import timezone


def dashboard_callback(request, context):
    """
    Populate the dashboard with role-appropriate KPI cards
    and quick-access links.
    """
    from core.models import Unit
    from support.models import Ticket
    from billing.models import Charge
    from collections_app.models import Payment
    from django.db.models import Sum, Count, Q, F, Min, ExpressionWrapper, DecimalField
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    user = request.user
    role = getattr(user, "role", "")
    is_super = user.is_superuser

    cards = []
    quick_links = []

    # Pre-calculate common metrics
    today = timezone.localdate()
    today_payments = Payment.objects.filter(paid_at__date=today)
    today_count = today_payments.count()
    today_total = (
        today_payments.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
    )
    total_revenue = (
        Payment.objects.aggregate(Sum("total_amount"))["total_amount__sum"] or 0
    )

    # ── Financial KPIs (Super, GM, FM) ──
    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER"):
        # أصل المديونية (إجمالي المبالغ المطلوبة)
        total_original_debt = (
            Charge.objects.filter(status=Charge.Status.PUBLISHED).aggregate(Sum("amount"))["amount__sum"] or 0
        )
        # باقي المديونية (الفرق بين المطلوب والمحصل)
        total_remaining_debt = total_original_debt - total_revenue

        # عدد الوحدات المتأخرة (باقي المديونية > 0)
        unpaid_units_count = Unit.objects.annotate(
            total_debt=Sum('charges__amount', filter=Q(charges__status=Charge.Status.PUBLISHED)),
            total_paid=Sum('charges__allocations__amount')
        ).filter(total_debt__gt=F('total_paid')).count()

        pending_charges = Charge.objects.filter(status=Charge.Status.PENDING).count()

        cards.append({
            "title": _("Total Revenue"),
            "metric": f"{total_revenue:,.2f} EGP",
            "footer": _("Collected from paid charges"),
            "icon": "payments",
            "color": "primary",
            "link": "/admin/collections_app/payment/",
        })
        cards.append({
            "title": _("Today's Collections"),
            "metric": f"{today_total:,.2f} EGP",
            "footer": f"{today_count} " + str(_("receipts today")),
            "icon": "receipt_long",
            "color": "success",
            "link": "/admin/daily-collections/",
        })
        cards.append({
            "title": _("Remaining Debt"),
            "metric": f"{total_remaining_debt:,.2f} EGP",
            "footer": _("Total outstanding balance"),
            "icon": "money_off",
            "color": "danger",
            "link": "/admin/core/unit/?has_balance=1",
        })
        cards.append({
            "title": _("Unpaid Units"),
            "metric": unpaid_units_count,
            "footer": _("Units with outstanding debt"),
            "icon": "person_off",
            "color": "warning",
            "link": "/admin/core/unit/?has_balance=1",
        })
    elif role == "DATA_ENTRY":
        # Data Entry sees Today's Collections & Total Original Debt
        total_original_debt = (
            Charge.objects.filter(status=Charge.Status.PUBLISHED).aggregate(Sum("amount"))["amount__sum"] or 0
        )
        cards.append({
            "title": _("Today's Collections"),
            "metric": f"{today_total:,.2f} EGP",
            "footer": f"{today_count} " + str(_("receipts today")),
            "icon": "receipt_long",
            "color": "success",
            "link": "/admin/daily-collections/",
        })
        cards.append({
            "title": _("Total Original Debt"),
            "metric": f"{total_original_debt:,.2f} EGP",
            "footer": _("Total of all published charges"),
            "icon": "account_balance",
            "color": "info",
            "link": "/admin/billing/charge/?status__exact=PUBLISHED",
        })

    # ── Operational KPIs (Super, GM, FM, Supervisor) ──
    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"):
        pass # Already calculated above

        cards.append({
            "title": _("Today's Collections"),
            "metric": f"{today_total:,.2f} EGP",
            "footer": f"{today_count} " + str(_("receipts today")),
            "icon": "receipt_long",
            "color": "success",
            "link": "/admin/daily-collections/",
        })

    # ── Support KPIs (Super, GM, Supervisor, Reception) ──
    if is_super or role in ("GENERAL_MANAGER", "SUPERVISOR", "RECEPTION"):
        open_tickets = Ticket.objects.filter(status=Ticket.Status.OPEN).count()
        cards.append({
            "title": _("Open Tickets"),
            "metric": open_tickets,
            "footer": _("Support requests awaiting action"),
            "icon": "support_agent",
            "color": "danger",
            "link": "/admin/support/ticket/?status__exact=OPEN",
        })

    # ── Collection & Debt Stats (Super, GM, FM, Supervisor) ──
    if is_super or role in (
        "GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"
    ):
        from imports.models import ExcelUpload

        uploaded_count = ExcelUpload.objects.filter(status="UPLOADED").count()
        cards.append({
            "title": _("Pending Imports"),
            "metric": uploaded_count,
            "footer": _("Excel files awaiting processing"),
            "icon": "upload_file",
            "color": "warning",
            "link": "/admin/imports/excelupload/",
        })

    # ── Units KPI (Super, GM) ──
    if is_super or role == "GENERAL_MANAGER":
        total_units = Unit.objects.count()
        cards.append({
            "title": _("Total Units"),
            "metric": total_units,
            "footer": _("Managed resort units"),
            "icon": "apartment",
            "color": "success",
            "link": "/admin/core/unit/",
        })

    # ────────────────────────────────────────────────
    #  Quick-Access Links (role-based)
    # ────────────────────────────────────────────────

    # Collections (Supervisor+ / Data Entry)
    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR", "DATA_ENTRY"):
        quick_links.append({
            "title": _("Daily Collections"),
            "link": "/admin/daily-collections/",
            "icon": "monitoring",
            "icon_color": "#16a34a",
            "bg": "#f0fdf4",
            "border": "#dcfce7",
        })
        quick_links.append({
            "title": _("Record Payment"),
            "link": "/admin/record-payment/",
            "icon": "add_card",
            "icon_color": "#059669",
            "bg": "#ecfdf5",
            "border": "#d1fae5",
        })

    # Financials (FM+)
    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER"):
        quick_links.append({
            "title": _("Billing & Charges"),
            "link": "/admin/billing/charge/",
            "icon": "request_quote",
            "icon_color": "#2563eb",
            "bg": "#eff6ff",
            "border": "#dbeafe",
        })
        quick_links.append({
            "title": _("Payments"),
            "link": "/admin/collections_app/payment/",
            "icon": "account_balance_wallet",
            "icon_color": "#7c3aed",
            "bg": "#f5f3ff",
            "border": "#ede9fe",
        })

    # Data Import (Supervisor+)
    if is_super or role in (
        "GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"
    ):
        quick_links.append({
            "title": _("Excel Import"),
            "link": "/admin/imports/excelupload/",
            "icon": "table_chart",
            "icon_color": "#d97706",
            "bg": "#fffbeb",
            "border": "#fef3c7",
        })

    # Support (Reception+)
    if is_super or role in ("GENERAL_MANAGER", "SUPERVISOR", "RECEPTION"):
        quick_links.append({
            "title": _("Support Tickets"),
            "link": "/admin/support/ticket/",
            "icon": "confirmation_number",
            "icon_color": "#dc2626",
            "bg": "#fef2f2",
            "border": "#fecaca",
        })

    # Users & Configuration (GM+)
    if is_super or role == "GENERAL_MANAGER":
        quick_links.append({
            "title": _("Users"),
            "link": "/admin/users/user/",
            "icon": "group",
            "icon_color": "#0891b2",
            "bg": "#ecfeff",
            "border": "#cffafe",
        })
        quick_links.append({
            "title": _("Units"),
            "link": "/admin/core/unit/",
            "icon": "villa",
            "icon_color": "#4f46e5",
            "bg": "#eef2ff",
            "border": "#e0e7ff",
        })
        quick_links.append({
            "title": _("Teams"),
            "link": "/admin/users/team/",
            "icon": "groups",
            "icon_color": "#0d9488",
            "bg": "#f0fdfa",
            "border": "#ccfbf1",
        })

    # Super Admin only
    if is_super:
        quick_links.append({
            "title": _("Resorts"),
            "link": "/admin/core/resort/",
            "icon": "holiday_village",
            "icon_color": "#be185d",
            "bg": "#fdf2f8",
            "border": "#fce7f3",
        })
        quick_links.append({
            "title": _("Owner Units"),
            "link": "/admin/core/ownerunit/",
            "icon": "real_estate_agent",
            "icon_color": "#9333ea",
            "bg": "#faf5ff",
            "border": "#f3e8ff",
        })

    # ── Sidebar Lists: Activity & Debtors (Supervisor+) ──
    recent_activity = []
    top_debtors = []
    if is_super or role in ("GENERAL_MANAGER", "FINANCIAL_MANAGER", "SUPERVISOR"):
        # Recent Activity (Movements)
        recent_activity = Payment.objects.select_related('unit', 'created_by').order_by('-created_at')[:10]
        
        # Top Debtors (Large amounts + Aging)
        now = timezone.now()
        top_debtors_qs = Unit.objects.annotate(
            total_debt=Sum('charges__amount', filter=Q(charges__status=Charge.Status.PUBLISHED)),
            total_paid=Sum('charges__allocations__amount', filter=Q(charges__status=Charge.Status.PUBLISHED))
        ).annotate(
            balance=ExpressionWrapper(F('total_debt') - F('total_paid'), output_field=DecimalField()),
            oldest_charge=Min('charges__created_at', filter=Q(charges__status=Charge.Status.PUBLISHED, charges__amount__gt=0))
        ).filter(balance__gt=0).order_by('-balance')[:50]

        for u in top_debtors_qs:
            aging_months = 0
            if u.oldest_charge:
                diff = relativedelta(now, u.oldest_charge)
                aging_months = diff.years * 12 + diff.months
            
            top_debtors.append({
                "unit": u,
                "balance": u.balance,
                "aging_months": aging_months,
                "unit_key": u.unit_key
            })

    context.update({
        "cards": cards,
        "quick_links": quick_links,
        "recent_activity": recent_activity,
        "top_debtors": top_debtors,
        "title": "Delta Sharm Operations Center",
        "subtitle": "",
    })

    return context
