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

from billing.models import Charge
from core.models import Notification, OwnerUnit
from core.notifications import notify_unit_counterparts, notify_user
from users.models import User

from .models import Payment, PaymentAllocation, PaymentSession

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

        # Only owners can initiate online payments
        if user.role != User.Role.OWNER:
            return Response(
                {"detail": "Only property owners may initiate online payments."},
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

        # Resolve unit IDs this owner is permitted to access
        owner_unit_ids = (
            OwnerUnit.objects.filter(owner=user, unit__is_active=True)
            .values_list("unit_id", flat=True)
        )

        # Fetch only charges that:
        #   - belong to the owner's units (prevents IDOR)
        #   - are in PUBLISHED status (prevents paying pending/rejected charges)
        #   - match the supplied IDs
        charges = (
            Charge.objects.filter(
                id__in=charge_ids,
                unit_id__in=owner_unit_ids,
                status=Charge.Status.PUBLISHED,
            )
            .select_related("unit", "unit__resort")
            .prefetch_related("allocations")
        )

        if not charges.exists():
            return Response(
                {"detail": "No valid published charges found for the supplied IDs."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Compute the exact remaining balance for each charge server-side
        total_amount = Decimal("0.00")
        payable_charge_ids: list[int] = []
        first_unit = None

        for charge in charges:
            remaining = charge.balance  # amount − allocated payments
            if remaining > Decimal("0.00"):
                total_amount += remaining
                payable_charge_ids.append(charge.pk)
                if first_unit is None:
                    first_unit = charge.unit

        if total_amount <= Decimal("0.00"):
            return Response(
                {"detail": "All selected charges have already been fully paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate a unique Paymob order identifier
        merchant_order_id = f"ORD-{uuid.uuid4().hex[:16].upper()}"

        # Persist the session so the webhook can retrieve it by merchant_order_id
        session = PaymentSession.objects.create(
            merchant_order_id=merchant_order_id,
            owner=user,
            resort=first_unit.resort,
            unit=first_unit,
            amount=total_amount,
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
            "Payment session created: merchant_order_id=%s owner=%s amount=%s",
            merchant_order_id,
            user.phone,
            total_amount,
        )

        return Response(
            {
                "merchant_order_id": merchant_order_id,
                "total_amount": str(total_amount),
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
                receipt_no = f"ONLINE-{transaction_id}"
                if Payment.objects.filter(receipt_no=receipt_no).exists():
                    logger.warning(
                        "Paymob webhook: duplicate transaction ID %s.",
                        transaction_id,
                    )
                    return Response({"status": "already_processed"})

                # ── 8. Retrieve stored charge IDs and re-validate ownership ──
                stored_charge_ids: list[int] = session.charge_ids

                charges = (
                    Charge.objects.filter(
                        id__in=stored_charge_ids,
                        unit=session.unit,
                        status=Charge.Status.PUBLISHED,
                    )
                    .select_related("resort", "unit")
                    .prefetch_related("allocations")
                    .order_by("year", "month", "id")
                )

                if not charges.exists():
                    logger.error(
                        "Paymob webhook: no valid charges found for session %s.",
                        merchant_order_id,
                    )
                    session.mark_failed()
                    return Response(
                        {"detail": "No valid charges found for this session."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # ── 9. Create Payment ledger entry using the SESSION amount ───
                # We use session.amount, NOT anything from the Paymob payload.
                payment = Payment.objects.create(
                    resort=session.resort,
                    unit=session.unit,
                    receipt_no=receipt_no,
                    total_amount=session.amount,
                    notes=f"Online payment via Paymob. Transaction ID: {transaction_id}",
                )

                # ── 10. FIFO allocation across stored charges ─────────────────
                remaining = session.amount
                for charge in charges:
                    if remaining <= Decimal("0.00"):
                        break
                    charge_balance = charge.balance
                    if charge_balance <= Decimal("0.00"):
                        continue
                    alloc_amount = min(remaining, charge_balance)
                    PaymentAllocation.objects.create(
                        payment=payment,
                        charge=charge,
                        amount=alloc_amount,
                    )
                    remaining -= alloc_amount

                # ── 11. Mark session complete ─────────────────────────────────
                session.mark_completed()

                # ── 12. Notify the payer, and the other party on this unit ────
                try:
                    notify_user(
                        session.owner,
                        title="Payment Successful",
                        body=f"Your payment of {session.amount} EGP for unit {session.unit.unit_key} was recorded. Receipt: {receipt_no}",
                        notif_type=Notification.Type.PAYMENT_SUCCESS,
                        data={"type": "payment_success", "receipt_no": receipt_no, "unit_id": session.unit_id},
                    )
                    payer_label = session.owner.fullname or session.owner.phone
                    notify_unit_counterparts(
                        session.unit,
                        acting_user=session.owner,
                        title="Unit Payment Received",
                        body=f"{payer_label} paid {session.amount} EGP for unit {session.unit.unit_key}. Receipt: {receipt_no}",
                        notif_type=Notification.Type.UNIT_ACTIVITY,
                        data={"type": "unit_payment_success", "receipt_no": receipt_no, "unit_id": session.unit_id},
                    )
                except Exception as task_err:
                    logger.warning(f"Failed to dispatch notifications: {task_err}")

                logger.info(
                    "Paymob webhook: payment recorded successfully. "
                    "receipt_no=%s session=%s amount=%s",
                    receipt_no,
                    merchant_order_id,
                    session.amount,
                )

            return Response(
                {"status": "success", "receipt_no": receipt_no},
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
