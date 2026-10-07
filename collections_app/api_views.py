"""
Payment API Views — Security-hardened implementation.

Architecture decisions:
  1. InitiateOnlinePaymentAPIView creates a PaymentSession record server-side,
     locking in the amount and charge_ids BEFORE sending the owner to Paymob.
  2. PaymentWebhookAPIView only trusts the merchant_order_id from Paymob.
     It loads the amount/charge_ids from the DB session — never from the POST body.
  3. Paymob HMAC-SHA512 signature is verified with hmac.compare_digest() before
     any business logic runs.
  4. PAYMENT_HMAC_KEY is a dedicated secret in .env, separate from Django SECRET_KEY.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Charge, PaymentDeferral
from core.models import Notification
from core.notifications import notify_unit_counterparts, notify_user
from users.models import User

from .models import Payment, PaymentAllocation, PaymentSession
from .payers import payer_snapshot
from .receipts import generate_receipt_pdf

logger = logging.getLogger("collections_app")


# ─── Paymob HMAC verification ────────────────────────────────────────────────


def _verify_paymob_hmac(payload: dict, received_hmac: str) -> bool:
    """
    Reconstruct and verify the Paymob HMAC-SHA512 signature.

    Paymob signs a specific concatenated string of transaction fields.
    Reference: https://docs.paymob.com/docs/transaction-webhooks

    The HMAC_SECRET set in Paymob's dashboard must equal settings.PAYMENT_HMAC_KEY.
    """
    hmac_key: str = getattr(settings, "PAYMENT_HMAC_KEY", "")
    if not hmac_key:
        logger.error("PAYMENT_HMAC_KEY is not configured in settings.")
        return False

    # Paymob's canonical field order for HMAC construction
    fields = [
        str(payload.get("amount_cents", "")),
        str(payload.get("created_at", "")),
        str(payload.get("currency", "")),
        str(payload.get("error_occured", "")),
        str(payload.get("has_parent_transaction", "")),
        str(payload.get("id", "")),
        str(payload.get("integration_id", "")),
        str(payload.get("is_3d_secure", "")),
        str(payload.get("is_auth", "")),
        str(payload.get("is_capture", "")),
        str(payload.get("is_refunded", "")),
        str(payload.get("is_standalone_payment", "")),
        str(payload.get("is_voided", "")),
        str(payload.get("order", {}).get("id", "") if isinstance(payload.get("order"), dict) else ""),
        str(payload.get("owner", "")),
        str(payload.get("pending", "")),
        str(payload.get("source_data", {}).get("pan", "") if isinstance(payload.get("source_data"), dict) else ""),
        str(payload.get("source_data", {}).get("sub_type", "") if isinstance(payload.get("source_data"), dict) else ""),
        str(payload.get("source_data", {}).get("type", "") if isinstance(payload.get("source_data"), dict) else ""),
        str(payload.get("success", "")),
    ]
    concatenated = "".join(fields)

    expected_hmac = hmac.new(
        hmac_key.encode("utf-8"),
        concatenated.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(expected_hmac, received_hmac)


# ─── Views ───────────────────────────────────────────────────────────────────


class InitiateOnlinePaymentAPIView(APIView):
    """
    Step 1 of the online payment flow.

    Validates that the requested charges belong to the authenticated owner,
    calculates the exact total server-side, persists a PaymentSession, then
    returns the Paymob checkout URL.

    The client MUST NOT compute or send the amount — this endpoint does it.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "payment"

    @extend_schema(
        summary="Initiate Online Payment Session",
        description=(
            "Validates charge ownership, calculates exact totals server-side, "
            "creates a PaymentSession record, and returns the Paymob checkout URL. "
            "The client sends only charge IDs — never amounts."
        ),
        responses={200: "Payment Session Data"},
    )
    def post(self, request):
        user = request.user

        # Owners and Tenants can pay online — a tenant has to be able to settle
        # their own utility months to get their clearance statement. What each
        # may pay is exactly what they can see (see _accessible_charges_qs).
        if user.role not in (User.Role.OWNER, User.Role.TENANT):
            return Response(
                {"detail": "Only property owners and tenants may initiate online payments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        charge_ids = request.data.get("charge_ids")
        if not charge_ids or not isinstance(charge_ids, list):
            return Response(
                {"detail": "charge_ids must be a non-empty list of integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure every supplied ID is a positive integer (prevent type confusion)
        try:
            charge_ids = [int(cid) for cid in charge_ids]
        except (TypeError, ValueError):
            return Response(
                {"detail": "charge_ids must contain only integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch only charges that:
        #   - the caller can see — their own units, PUBLISHED, and for a
        #     Tenant only their lease's utility months; for an Owner never the
        #     months a long lease moved to its tenant (prevents IDOR and
        #     paying someone else's charges)
        #   - match the supplied IDs
        from billing.views import _accessible_charges_qs

        accessible, _unit_ids = _accessible_charges_qs(user)
        charges = (
            accessible.filter(id__in=charge_ids, unit__is_active=True)
            .select_related("unit", "unit__resort")
            .prefetch_related("allocations")
        )

        if not charges.exists():
            return Response(
                {"detail": "No valid published charges found for the supplied IDs."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Combining charges from more than one unit into a single payment is
        # allowed (each unit still gets its own Payment/receipt at webhook
        # time — see PaymentWebhookAPIView), but only within one resort: a
        # single Paymob transaction/receipt set spanning two different
        # villages has no clean audit story.
        charges_by_id = {c.pk: c for c in charges}
        resort_ids = {c.unit.resort_id for c in charges}
        if len(resort_ids) > 1:
            return Response(
                {"detail": "Selected charges must all belong to the same resort."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        unit_ids = {c.unit_id for c in charges}
        common_unit = charges[0].unit if len(unit_ids) == 1 else None

        # Compute the exact remaining balance for each charge server-side,
        # preserving the order the owner selected them in — that order
        # becomes the FIFO/priority order across units too (used both for
        # a partial payment here and for allocation at webhook time).
        total_due = Decimal("0.00")
        payable_charge_ids: list[int] = []
        for cid in charge_ids:
            charge = charges_by_id.get(cid)
            if charge is None:
                continue
            remaining = charge.balance  # amount − allocated payments
            if remaining > Decimal("0.00"):
                total_due += remaining
                payable_charge_ids.append(charge.pk)

        if total_due <= Decimal("0.00"):
            return Response(
                {"detail": "All selected charges have already been fully paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Optional partial payment: the owner pays less than the full due
        # now and commits to a date for the rest (self-service, capped at
        # 5 days — looser than ChargeDeferView's 3-day cap since this is
        # backed by a real payment already made, not a free-standing
        # request; anything longer needs the accountant or a support ticket).
        pay_amount_raw = request.data.get("pay_amount")
        if pay_amount_raw is None:
            pay_amount = total_due
        else:
            try:
                pay_amount = Decimal(str(pay_amount_raw))
            except Exception:
                return Response({"detail": "pay_amount must be a valid decimal."}, status=status.HTTP_400_BAD_REQUEST)
            if pay_amount <= Decimal("0.00") or pay_amount > total_due:
                return Response(
                    {"detail": "pay_amount must be greater than 0 and no more than the total due."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        remaining_due_date = None
        if pay_amount < total_due:
            remaining_due_date_raw = request.data.get("remaining_due_date")
            if not remaining_due_date_raw:
                return Response(
                    {"detail": "remaining_due_date is required when pay_amount is less than the total due."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                remaining_due_date = timezone.datetime.strptime(str(remaining_due_date_raw), "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "remaining_due_date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
            today = timezone.localdate()
            if remaining_due_date <= today or remaining_due_date > today + timedelta(days=5):
                return Response(
                    {"detail": "remaining_due_date must be within the next 5 days. For longer, contact the resort's accountant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Generate a unique Paymob order identifier
        merchant_order_id = f"ORD-{uuid.uuid4().hex[:16].upper()}"

        # Persist the session so the webhook can retrieve it by merchant_order_id
        session = PaymentSession.objects.create(
            merchant_order_id=merchant_order_id,
            owner=user,
            resort=charges[0].unit.resort,
            unit=common_unit,
            amount=pay_amount,
            remaining_due_date=remaining_due_date,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        session.charge_ids = payable_charge_ids
        session.save(update_fields=["_charge_ids_json"])

        # Return session metadata plus Paymob checkout URL
        # The iframe URL / payment token would be obtained from Paymob's order
        # registration API in a production implementation.
        paymob_iframe_id = getattr(settings, "PAYMOB_IFRAME_ID", "")
        checkout_url = (
            f"https://accept.paymob.com/api/acceptance/iframes/{paymob_iframe_id}"
            f"?payment_token=REPLACE_WITH_PAYMOB_TOKEN"
        )

        logger.info(
            "Payment session created: merchant_order_id=%s owner=%s amount=%s total_due=%s",
            merchant_order_id,
            user.phone,
            pay_amount,
            total_due,
        )

        return Response(
            {
                "merchant_order_id": merchant_order_id,
                "total_amount": str(pay_amount),
                "total_due": str(total_due),
                "remaining_due_date": remaining_due_date.isoformat() if remaining_due_date else None,
                "currency": "EGP",
                "charge_count": len(payable_charge_ids),
                "expires_at": session.expires_at.isoformat(),
                "checkout_url": checkout_url,
            },
            status=status.HTTP_200_OK,
        )


class PaymentWebhookAPIView(APIView):
    """
    Step 2 of the online payment flow — Paymob Transaction Webhook.

    Security model:
      1. HMAC-SHA512 signature is verified FIRST using hmac.compare_digest().
         Any mismatch → 403. No business logic runs.
      2. The PaymentSession is loaded by merchant_order_id from the database.
         The webhook NEVER reads amount or charge_ids from the POST body.
      3. A select_for_update() lock prevents duplicate processing under concurrent
         webhook deliveries.
      4. The Payment + PaymentAllocation records are created inside a single
         atomic transaction.
    """

    permission_classes = [AllowAny]
    # Exempt from CSRF — webhook is machine-to-machine
    authentication_classes = []

    @extend_schema(
        summary="Paymob Payment Webhook Callback",
        description=(
            "Receives the Paymob HMAC-signed transaction notification. "
            "Verifies the signature, retrieves the stored PaymentSession, "
            "and atomically issues Payment + Allocation ledger entries."
        ),
    )
    def post(self, request):
        # ── 1. Extract and verify HMAC signature ────────────────────────────
        received_hmac = (
            request.query_params.get("hmac")
            or request.headers.get("X-Signature", "")
        )

        if not received_hmac:
            logger.warning("Paymob webhook received with no HMAC header.")
            return Response(
                {"detail": "Missing HMAC signature."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload: dict = request.data if isinstance(request.data, dict) else {}

        if not _verify_paymob_hmac(payload, received_hmac):
            logger.warning(
                "Paymob webhook HMAC verification FAILED. "
                "Possible forgery attempt. Remote IP: %s",
                request.META.get("REMOTE_ADDR"),
            )
            return Response(
                {"detail": "Invalid HMAC signature."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── 2. Check transaction success flag ────────────────────────────────
        is_success: bool = bool(payload.get("success", False))
        transaction_id = str(payload.get("id", ""))

        if not is_success:
            logger.info("Paymob webhook: transaction %s was not successful.", transaction_id)
            return Response({"status": "ignored", "reason": "payment_not_successful"})

        # ── 3. Resolve merchant_order_id from Paymob's order object ─────────
        order_obj = payload.get("order") or {}
        merchant_order_id: str = (
            order_obj.get("merchant_order_id", "")
            if isinstance(order_obj, dict)
            else ""
        )

        if not merchant_order_id:
            logger.error(
                "Paymob webhook: successful transaction %s has no merchant_order_id.",
                transaction_id,
            )
            return Response(
                {"detail": "merchant_order_id missing from payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── 4. Load the server-side PaymentSession (never trust the POST body) ──
        try:
            # select_for_update prevents a race condition where two concurrent
            # webhook deliveries both see status=PENDING and both create ledger entries
            with transaction.atomic():
                session = (
                    PaymentSession.objects.select_related("owner", "resort", "unit")
                    .select_for_update()
                    .get(merchant_order_id=merchant_order_id)
                )

                # ── 5. Guard: already processed ─────────────────────────────
                if session.status == PaymentSession.Status.COMPLETED:
                    logger.info(
                        "Paymob webhook: session %s already completed — skipping duplicate.",
                        merchant_order_id,
                    )
                    return Response({"status": "already_processed"})

                # ── 6. Guard: session expired ────────────────────────────────
                if session.is_expired:
                    session.mark_failed()
                    logger.warning(
                        "Paymob webhook: session %s has expired.",
                        merchant_order_id,
                    )
                    return Response(
                        {"detail": "Payment session has expired."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # ── 7. Guard: duplicate receipt by Paymob transaction ID ─────
                # Base id for this transaction — a single-unit session keeps
                # this exact string as its one Payment's receipt_no (same
                # format as before); a multi-unit session suffixes it per
                # unit below, so the guard matches by prefix either way.
                receipt_no_base = f"ONLINE-{transaction_id}"
                if Payment.objects.filter(receipt_no__startswith=receipt_no_base).exists():
                    logger.warning(
                        "Paymob webhook: duplicate transaction ID %s.",
                        transaction_id,
                    )
                    return Response({"status": "already_processed"})

                # ── 8. Retrieve stored charge IDs and re-validate ownership ──
                # Resort-scoped (not unit-scoped) so this works for both a
                # single-unit session and a combined multi-unit one — the
                # resort match is the real ownership/tenant-isolation
                # guarantee here, re-validated server-side same as before.
                stored_charge_ids: list[int] = session.charge_ids

                charges_qs = (
                    Charge.objects.filter(
                        id__in=stored_charge_ids,
                        resort=session.resort,
                        status=Charge.Status.PUBLISHED,
                    )
                    .select_related("resort", "unit")
                    .prefetch_related("allocations")
                )
                charges_by_id = {c.pk: c for c in charges_qs}
                # Re-sort into the order the owner originally selected them —
                # that order is the FIFO/priority order across units too.
                charges = [charges_by_id[cid] for cid in stored_charge_ids if cid in charges_by_id]

                if not charges:
                    logger.error(
                        "Paymob webhook: no valid charges found for session %s.",
                        merchant_order_id,
                    )
                    session.mark_failed()
                    return Response(
                        {"detail": "No valid charges found for this session."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # ── 9. FIFO allocation across stored charges, using the
                # SESSION amount (never anything from the Paymob payload) ──
                allocations: list[tuple] = []  # (charge, alloc_amount)
                remaining = session.amount
                for charge in charges:
                    if remaining <= Decimal("0.00"):
                        break
                    charge_balance = charge.balance
                    if charge_balance <= Decimal("0.00"):
                        continue
                    alloc_amount = min(remaining, charge_balance)
                    allocations.append((charge, alloc_amount))
                    remaining -= alloc_amount

                # ── 10. Create one Payment per unit touched — each unit
                # gets its own receipt/PDF, even within one transaction ──
                touched_unit_ids = list(dict.fromkeys(c.unit_id for c, _ in allocations))
                multi_unit = len(touched_unit_ids) > 1
                payments = []
                for unit_id in touched_unit_ids:
                    unit_allocations = [(c, amt) for c, amt in allocations if c.unit_id == unit_id]
                    unit = unit_allocations[0][0].unit
                    unit_total = sum((amt for _, amt in unit_allocations), Decimal("0.00"))
                    unit_receipt_no = f"{receipt_no_base}-{unit_id}" if multi_unit else receipt_no_base
                    payment = Payment.objects.create(
                        resort=session.resort,
                        unit=unit,
                        receipt_no=unit_receipt_no,
                        total_amount=unit_total,
                        notes=f"Online payment via Paymob. Transaction ID: {transaction_id}",
                        **payer_snapshot(session.owner),
                    )
                    for charge, amt in unit_allocations:
                        PaymentAllocation.objects.create(payment=payment, charge=charge, amount=amt)
                    payments.append(payment)

                # ── 11. Any charge this payment didn't fully cover gets
                # auto-deferred to the owner-chosen date (partial payment) ──
                deferred_charges = []
                if session.remaining_due_date:
                    for charge in charges:
                        # charge.balance queries allocations fresh each time,
                        # so it already reflects the PaymentAllocation rows
                        # just created above within this same transaction.
                        if charge.balance > Decimal("0.00"):
                            PaymentDeferral.objects.create(
                                charge=charge,
                                requested_by=session.owner,
                                deferred_to=session.remaining_due_date,
                                status=PaymentDeferral.Status.AUTO_APPROVED,
                                decided_by=session.owner,
                                decided_at=timezone.now(),
                            )
                            deferred_charges.append(charge)

                # ── 12. Mark session complete ─────────────────────────────────
                session.mark_completed()

                # ── 13. Notify the payer, and the other party on each unit ────
                try:
                    for payment in payments:
                        notify_user(
                            session.owner,
                            title="Payment Successful",
                            body=f"Your payment of {payment.total_amount} EGP for unit {payment.unit.unit_key} was recorded. Receipt: {payment.receipt_no}",
                            notif_type=Notification.Type.PAYMENT_SUCCESS,
                            data={"type": "payment_success", "receipt_no": payment.receipt_no, "unit_id": payment.unit_id},
                        )
                        payer_label = session.owner.fullname or session.owner.phone
                        notify_unit_counterparts(
                            payment.unit,
                            acting_user=session.owner,
                            title="Unit Payment Received",
                            body=f"{payer_label} paid {payment.total_amount} EGP for unit {payment.unit.unit_key}. Receipt: {payment.receipt_no}",
                            notif_type=Notification.Type.UNIT_ACTIVITY,
                            data={"type": "unit_payment_success", "receipt_no": payment.receipt_no, "unit_id": payment.unit_id},
                        )
                    for charge in deferred_charges:
                        payer_label = session.owner.fullname or session.owner.phone
                        notify_user(
                            session.owner,
                            title="Payment Deferred",
                            body=f"The remaining balance for {charge.unit.unit_key} was scheduled for {session.remaining_due_date}.",
                            notif_type=Notification.Type.PAYMENT_DEFERRED,
                            data={"type": "payment_deferred", "charge_id": charge.id},
                        )
                        notify_unit_counterparts(
                            charge.unit,
                            acting_user=session.owner,
                            title="Unit Payment Deferred",
                            body=f"{payer_label} scheduled the remaining balance for unit {charge.unit.unit_key} to {session.remaining_due_date}.",
                            notif_type=Notification.Type.UNIT_ACTIVITY,
                            data={"type": "unit_payment_deferred", "charge_id": charge.id},
                        )
                except Exception as task_err:
                    logger.warning(f"Failed to dispatch notifications: {task_err}")

                logger.info(
                    "Paymob webhook: payment recorded successfully. "
                    "receipt_no_base=%s session=%s amount=%s payments=%s",
                    receipt_no_base,
                    merchant_order_id,
                    session.amount,
                    len(payments),
                )

            # Generated after the transaction commits — PDF rendering is
            # slow-ish and must not hold the row lock, and a rendering bug
            # must never roll back a payment that already succeeded.
            for payment in payments:
                generate_receipt_pdf(payment)

            return Response(
                {"status": "success", "receipt_no": receipt_no_base, "receipts": [p.receipt_no for p in payments]},
                status=status.HTTP_201_CREATED,
            )

        except PaymentSession.DoesNotExist:
            logger.error(
                "Paymob webhook: PaymentSession not found for merchant_order_id=%s",
                merchant_order_id,
            )
            return Response(
                {"detail": "Payment session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.exception(
                "Paymob webhook: unexpected error for merchant_order_id=%s",
                merchant_order_id,
            )
            # Return 500 so Paymob retries — do NOT expose internal error detail
            return Response(
                {"detail": "Internal server error. Payment will be retried."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
