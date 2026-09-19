from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.http import HttpResponseForbidden
from collections_app.models import Payment, PaymentAllocation
from collections_app.receipts import generate_receipt_pdf
from billing.models import Charge


def _can_access_collections(user):
    return user.is_superuser or (
        hasattr(user, "role") and user.role in ["SUPERVISOR", "GENERAL_MANAGER", "FINANCIAL_MANAGER", "DATA_ENTRY"]
    )


@staff_member_required
def daily_collections_view(request):
    if not _can_access_collections(request.user):
        return HttpResponseForbidden("ليس لديك صلاحية للوصول لهذه الصفحة")

    today = timezone.now().date()
    mode = "day"
    selected_date = today

    date_param = request.GET.get("date")
    month_param = request.GET.get("month")

    if month_param:
        mode = "month"
        selected_month = month_param
        try:
            start_dt = datetime.strptime(selected_month, "%Y-%m").date()
        except ValueError:
            start_dt = today.replace(day=1)
        end_dt = (start_dt + timedelta(days=32)).replace(day=1)
        date_filter = {"paid_at__date__gte": start_dt, "paid_at__date__lt": end_dt}
        label = start_dt.strftime("%B %Y")
    elif date_param:
        mode = "day"
        try:
            selected_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
        date_filter = {"paid_at__date": selected_date}
        label = selected_date.strftime("%Y-%m-%d")
    else:
        mode = "day"
        selected_date = today
        date_filter = {"paid_at__date": selected_date}
        label = selected_date.strftime("%Y-%m-%d")

    payments_qs = (
        Payment.objects.filter(**date_filter)
        .select_related("resort", "unit", "created_by")
        .prefetch_related(
            "allocations", "allocations__charge", "unit__owner_units", "unit__owner_units__owner"
        )
        .annotate(
            allocated_sum=Coalesce(
                Sum("allocations__amount"),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("-paid_at")
    )

    # IDOR fix: this view previously showed payments from every resort to any
    # staff member who could reach it. Non-superusers only ever see their own
    # resort's collections.
    if not request.user.is_superuser:
        payments_qs = payments_qs.filter(resort=request.user.resort)

    payments = payments_qs.all()
    total_amount = sum(p.total_amount for p in payments)

    # Determine target year for operational summaries
    if mode == "month":
        target_year = start_dt.year
    else:
        target_year = selected_date.year

    # --------------------------------------------------------------------------
    # 2. KPI: Original Debt (Global context for this resort/year)
    # --------------------------------------------------------------------------
    # Non-superusers are always locked to their own resort. This mirrors the
    # TenantMiddleware fix: a staff member must never be able to see another
    # resort's totals just because their own `resort` field happens to be
    # unset, so we filter explicitly rather than only when a resort is present.
    charge_filter = {"year": target_year, "status": Charge.Status.PUBLISHED}
    if not request.user.is_superuser:
        charge_filter["resort"] = request.user.resort

    charges_agg = (
        Charge.objects.filter(**charge_filter)
        .annotate(
            paid_so_far=Coalesce(
                Sum("allocations__amount"),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
    )
    original_debt = sum(c.amount for c in charges_agg)
    
    # Remaining for the global context
    total_paid_all_time = sum(c.paid_so_far for c in charges_agg)
    remaining_debt = original_debt - total_paid_all_time
    if remaining_debt < 0:
        remaining_debt = Decimal("0.00")

    # Resort breakdown
    resort_breakdown = {}
    for p in payments:
        name = p.resort.name if p.resort else "—"
        if name not in resort_breakdown:
            resort_breakdown[name] = {"count": 0, "amount": Decimal("0.00")}
        resort_breakdown[name]["count"] += 1
        resort_breakdown[name]["amount"] += p.total_amount

    is_today = (mode == "day" and selected_date == today)

    # Navigation Labels
    prev_label = "اليوم السابق" if mode == "day" else "الشهر السابق"
    next_label = "اليوم التالي" if mode == "day" else "الشهر التالي"
    mode_icon = "event" if mode == "day" else "date_range"

    # Navigation Links
    if mode == "day":
        prev_dt = selected_date - timedelta(days=1)
        next_dt = selected_date + timedelta(days=1)
        prev_link = f"?date={prev_dt.strftime('%Y-%m-%d')}"
        next_link = f"?date={next_dt.strftime('%Y-%m-%d')}"
        can_go_next = selected_date < today
    else:
        y, m = int(month_param.split("-")[0]), int(month_param.split("-")[1])
        
        prev_m = m - 1
        prev_y = y
        if prev_m == 0:
            prev_m = 12
            prev_y -= 1
        prev_dt = datetime(prev_y, prev_m, 1).date()

        next_m = m + 1
        next_y = y
        if next_m == 13:
            next_m = 1
            next_y += 1
        next_dt = datetime(next_y, next_m, 1).date()
        
        prev_link = f"?month={prev_dt.strftime('%Y-%m')}"
        next_link = f"?month={next_dt.strftime('%Y-%m')}"
        can_go_next = (datetime(y, m, 1).date() < today.replace(day=1))

    context = {
        "title": "التحصيلات اليومية" if mode == "day" else "تقرير التحصيلات الشهري",
        "payments": payments,
        "total_amount": total_amount,
        "total_count": payments_qs.count(),
        "original_debt": original_debt,
        "remaining_debt": remaining_debt,
        "resort_breakdown": resort_breakdown,
        "prev_link": prev_link,
        "next_link": next_link,
        "prev_label": prev_label,
        "next_label": next_label,
        "mode_icon": mode_icon,
        "label": label,
        "mode": mode,
        "selected_date": selected_date.strftime("%Y-%m-%d") if mode == "day" else "",
        "selected_month": month_param if mode == "month" else "",
        "is_today": is_today,
        "can_go_next": can_go_next,
        "payment_history": payment_history if 'payment_history' in locals() else [],
    }
    return render(request, "admin/collections_app/daily_collections.html", context)


@staff_member_required
def record_payment_view(request):
    if not _can_access_collections(request.user):
        return HttpResponseForbidden("ليس لديك صلاحية للوصول لهذه الصفحة")

    from core.models import Unit
    from billing.models import Charge
    from django.db.models import Q
    from django.db import transaction
    
    search_query = request.GET.get("q", "").strip()
    unit_id = request.GET.get("unit_id") or request.POST.get("target_unit_id")
    
    units = []
    selected_unit = None
    debt_by_type = {}
    total_debt = Decimal("0.00")
    total_remaining = Decimal("0.00")
    
    # 1. Search Logic
    if search_query:
        units_qs = Unit.objects.filter(
            Q(unit_key__icontains=search_query) |
            Q(building_no__icontains=search_query) |
            Q(unit_no__icontains=search_query) |
            Q(owner_units__owner__phone__icontains=search_query)
        ).select_related("resort").distinct()
        # Cross-tenant fix: a non-superuser must not be able to search up
        # units belonging to another resort.
        if not request.user.is_superuser:
            units_qs = units_qs.filter(resort=request.user.resort)
        units = units_qs[:10]

    # 2. Selection & Debt Calculation
    if unit_id:
        selected_unit_qs = Unit.objects.filter(id=unit_id)
        # Cross-tenant fix: block selecting/recording a payment against a unit
        # from another resort just by guessing/passing its unit_id.
        if not request.user.is_superuser:
            selected_unit_qs = selected_unit_qs.filter(resort=request.user.resort)
        selected_unit = selected_unit_qs.first()
        if selected_unit:
            # Fetch all charges that are PUBLISHED and not rejected
            charges = Charge.objects.filter(
                unit=selected_unit,
                status=Charge.Status.PUBLISHED
            ).annotate(
                paid_so_far=Coalesce(
                    Sum("allocations__amount"),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ).order_by("year", "month")
            
            # Group by Type and calculate remaining
            for charge in charges:
                rem = charge.amount - charge.paid_so_far
                if rem > 0:
                    t_key = charge.type
                    if t_key not in debt_by_type:
                        debt_by_type[t_key] = {
                            "label": charge.get_type_display(),
                            "charges": [],
                            "total_rem": Decimal("0.00")
                        }
                    debt_by_type[t_key]["charges"].append(charge)
                    debt_by_type[t_key]["total_rem"] += rem
                    total_remaining += rem
                    total_debt += charge.amount

            # 3. Unit Transaction History (Unit Statement)
            payment_history = Payment.objects.filter(
                unit=selected_unit
            ).select_related("created_by").order_by("-paid_at")[:15]

    # 3. Payment Processing (POST)
    payment_success = False
    last_receipt = ""
    paid_amount = Decimal("0.00")
    
    if request.method == "POST" and selected_unit:
        receipt_no = request.POST.get("receipt_no")
        
        # Calculate total being paid
        total_payment_amount = Decimal("0.00")
        allocations_to_create = []
        
        # Iterate over types to allocate
        for t_key, data in debt_by_type.items():
            input_amount_str = request.POST.get(f"amount_{t_key}", "0")
            try:
                type_amount = Decimal(input_amount_str)
            except:
                type_amount = Decimal("0.00")
            
            if type_amount > 0:
                total_payment_amount += type_amount
                
                # FIFO Allocation
                remaining_to_allocate = type_amount
                for charge in data["charges"]:
                    if remaining_to_allocate <= 0:
                        break
                        
                    charge_rem = charge.amount - charge.paid_so_far
                    allocate = min(remaining_to_allocate, charge_rem)
                    
                    allocations_to_create.append({
                        "charge": charge,
                        "amount": allocate
                    })
                    remaining_to_allocate -= allocate

        if total_payment_amount > 0 and receipt_no:
            # Create Payment
            # NOTE: Payment/PaymentAllocation are imported at module level.
            # A local "from collections_app.models import Payment, ..." import
            # used to live here — Python then treats `Payment` as a local
            # name for the WHOLE function, so the `payment_history = Payment.
            # objects.filter(...)` line above (which runs earlier, on every
            # GET) raised UnboundLocalError. This is the exact traceback
            # recorded in django_errors.log. Removing the shadowing import
            # fixes it.
            with transaction.atomic():
                payment = Payment.objects.create(
                    resort=selected_unit.resort,
                    unit=selected_unit,
                    receipt_no=receipt_no,
                    total_amount=total_payment_amount,
                    created_by=request.user,
                    paid_at=timezone.now()
                )
                
                for alloc_data in allocations_to_create:
                    PaymentAllocation.objects.create(
                        payment=payment,
                        charge=alloc_data["charge"],
                        amount=alloc_data["amount"]
                    )

            generate_receipt_pdf(payment)

            payment_success = True
            last_receipt = receipt_no
            paid_amount = total_payment_amount
            
            # Refresh Debt Display after payment
            # (Re-running the logic above would be cleaner, but for now we just rely on redirect or refresh. 
            # Actually, to show updated "Remaining", we should re-calculate. 
            # Ideally we redirect to the same page with success flag to avoid double post)
            
            # For simplicity in this turn, I will just re-calculate debt by executing logic #2 again conceptually
            # OR I can just rely on the template showing the 'success message' 
            # and the user navigating again. 
            # But let's re-fetch to update the UI "Remaining" immediately.
            debt_by_type = {} 
            total_remaining = Decimal("0.00")
            # Re-fetch charges
            charges = Charge.objects.filter(
                unit=selected_unit,
                status=Charge.Status.PUBLISHED
            ).annotate(
                paid_so_far=Coalesce(
                    Sum("allocations__amount"),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ).order_by("year", "month")
            for charge in charges:
                 rem = charge.amount - charge.paid_so_far
                 if rem > 0:
                     t_key = charge.type
                     if t_key not in debt_by_type:
                         debt_by_type[t_key] = {
                             "label": charge.get_type_display(),
                             "charges": [],
                             "total_rem": Decimal("0.00")
                         }
                     debt_by_type[t_key]["charges"].append(charge)
                     debt_by_type[t_key]["total_rem"] += rem
                     total_remaining += rem
            

    context = {
        "title": "تسجيل عملية تحصيل",
        "search_query": search_query,
        "units": units,
        "selected_unit": selected_unit,
        "debt_by_type": debt_by_type,
        "total_debt": total_debt,
        "total_remaining": total_remaining,
        "payment_success": payment_success,
        "last_receipt": last_receipt,
        "paid_amount": paid_amount,
    }
    return render(request, "admin/collections_app/record_payment.html", context)
