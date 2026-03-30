from datetime import datetime, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, F, Q, Count
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.template.response import TemplateResponse
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import Unit, OwnerUnit
from billing.models import Charge
from collections_app.models import Payment

User = get_user_model()

@staff_member_required
def unit_search_view(request):
    query = request.GET.get("q", "").strip()
    resort = request.user.resort
    results = []
    search_type = "unit"

    if query and resort:
        # Search by unit key, building, or unit no
        unit_matches = Unit.objects.filter(
            resort=resort
        ).filter(
            Q(unit_key__icontains=query) | 
            Q(building_no__icontains=query) | 
            Q(unit_no__icontains=query)
        ).distinct()

        # Search by owner name
        owner_matches = User.objects.filter(
            resort=resort,
            role=User.Role.OWNER,
            fullname__icontains=query
        )

        if owner_matches.exists() and not unit_matches.exists():
            search_type = "owner"
            # Get all units for these owners
            results = Unit.objects.filter(
                owner_units__owner__in=owner_matches
            ).distinct().select_related('resort')
        else:
            results = unit_matches.select_related('resort')

    return render(request, "core/unit_search.html", {
        "query": query,
        "results": results,
        "search_type": search_type,
        "title": "بحث الوحدات والادارة",
    })

@staff_member_required
def unit_detail_view(request, unit_id):
    resort = request.user.resort
    unit = get_object_or_404(Unit, id=unit_id, resort=resort)
    
    # Last 12 months history
    one_year_ago = timezone.now() - timedelta(days=365)
    
    charges = Charge.objects.filter(
        unit=unit,
        status=Charge.Status.PUBLISHED,
        created_at__gte=one_year_ago
    ).order_by('-year', '-month')
    
    payments = Payment.objects.filter(
        unit=unit,
        paid_at__gte=one_year_ago
    ).order_by('-paid_at')
    
    # Calculate Balance
    total_debt = Charge.objects.filter(
        unit=unit, 
        status=Charge.Status.PUBLISHED
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_paid = Payment.objects.filter(
        unit=unit
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    balance = total_debt - total_paid
    
    # Owner info
    owners = [ou.owner for ou in unit.owner_units.all()]

    return render(request, "core/unit_detail.html", {
        "unit": unit,
        "owners": owners,
        "charges": charges,
        "payments": payments,
        "balance": balance,
        "title": f"تفاصيل الوحدة: {unit.unit_key}",
    })

@staff_member_required
def unit_statement_view(request, unit_id: int):
    resort = request.user.resort
    unit = get_object_or_404(Unit, id=unit_id, resort=resort)

    today = timezone.localdate()
    default_from = today.replace(month=1, day=1)

    from_str = request.GET.get("from")
    to_str = request.GET.get("to")

    def parse(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return None

    date_from = parse(from_str) if from_str else default_from
    date_to = parse(to_str) if to_str else today

    dt_from = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
    dt_to = timezone.make_aware(datetime.combine(date_to, datetime.max.time()))

    charges = (
        Charge.objects
        .filter(unit=unit, status=Charge.Status.PUBLISHED, created_at__range=(dt_from, dt_to))
        .annotate(paid_total=Coalesce(Sum("allocations__amount"), 0))
        .annotate(remaining=F("amount") - F("paid_total"))
        .order_by("year", "month", "id")
    )

    payments = (
        Payment.objects
        .filter(unit=unit, paid_at__range=(dt_from, dt_to))
        .order_by("paid_at", "id")
    )

    total_due = sum((c.amount for c in charges), start=0)
    total_paid = sum((p.total_amount for p in payments), start=0)
    total_remaining = total_due - total_paid

    return render(request, "core/unit_statement.html", {
        "unit": unit,
        "date_from": date_from,
        "date_to": date_to,
        "charges": charges,
        "payments": payments,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
    })