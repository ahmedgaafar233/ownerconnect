from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone

from core.models import Unit
from billing.models import Charge
from collections_app.models import Payment


@staff_member_required
def unit_statement_view(request, unit_id: int):
    unit = get_object_or_404(Unit, id=unit_id)

    today = timezone.localdate()
    default_from = today.replace(month=1, day=1)  # من أول السنة حتى اليوم

    from_str = request.GET.get("from")
    to_str = request.GET.get("to")

    def parse(d):
        return datetime.strptime(d, "%Y-%m-%d").date()

    date_from = parse(from_str) if from_str else default_from
    date_to = parse(to_str) if to_str else today

    dt_from = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
    dt_to = timezone.make_aware(datetime.combine(date_to, datetime.max.time()))

    charges = (
        Charge.objects
        .filter(unit=unit, status=Charge.Status.PUBLISHED, approved_at__range=(dt_from, dt_to))
        .annotate(paid_total=Coalesce(Sum("allocations__amount"), 0))
        .annotate(remaining=F("amount") - F("paid_total"))
        .order_by("year", "month", "id")
    )

    payments = (
        Payment.objects
        .filter(unit=unit, paid_at__range=(dt_from, dt_to))
        .prefetch_related("allocations", "allocations__charge")
        .order_by("paid_at", "id")
    )

    total_due = sum((c.amount for c in charges), start=0)
    total_paid = sum((c.paid_total for c in charges), start=0)
    total_remaining = total_due - total_paid

    return TemplateResponse(request, "admin/statement.html", {
        "unit": unit,
        "date_from": date_from,
        "date_to": date_to,
        "charges": charges,
        "payments": payments,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
    })