import logging

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from billing.receipts import CHARGE_TYPE_LABELS_AR

logger = logging.getLogger("collections_app.receipts")


_ROLE_LABELS_EN = {"OWNER": "Owner", "TENANT": "Tenant"}
_ROLE_LABELS_AR = {"OWNER": "مالك", "TENANT": "مستأجر"}


def _payer_for(payment):
    """
    The name and role printed on the receipt. A payment records who paid; one
    from before that was recorded falls back to the unit's owner, as every
    receipt used to say.
    """
    if payment.payer_name:
        return payment.payer_name, payment.payer_role

    from users.models import User

    owner_unit = (
        payment.unit.owner_units.filter(owner__role=User.Role.OWNER).select_related("owner").first()
    )
    if owner_unit is None:
        return "", ""
    owner = owner_unit.owner
    return owner.fullname or owner.phone, User.Role.OWNER


def generate_receipt_pdf(payment):
    """
    Renders and stores the payment's PDF receipt exactly once, at payment
    time — the legal record of what was paid, so it must never be
    regenerated later even if the underlying charges get edited.

    Best-effort: logs and returns on any failure rather than raising, since
    a receipt-rendering bug must never fail or roll back the payment record
    itself (callers run this after their transaction.atomic() block exits).
    """
    try:
        import weasyprint
        payer_name, payer_role = _payer_for(payment)

        is_online = payment.receipt_no.startswith("ONLINE-")

        html = render_to_string(
            "collections_app/receipt.html",
            {
                "payment": payment,
                "unit": payment.unit,
                "resort": payment.resort,
                "payer_name": payer_name,
                "payer_role_en": _ROLE_LABELS_EN.get(payer_role, ""),
                "payer_role_ar": _ROLE_LABELS_AR.get(payer_role, ""),
                "allocations": payment.allocations.select_related("charge").all(),
                "channel_label_ar": "دفع أونلاين" if is_online else "دفع نقدي / تحويل",
                "channel_label_en": "Online Payment" if is_online else "Cash / Bank Transfer",
                "charge_type_ar": CHARGE_TYPE_LABELS_AR,
            },
        )
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        payment.receipt_pdf.save(f"receipt-{payment.id}.pdf", ContentFile(pdf_bytes), save=True)
    except Exception:
        logger.exception("Failed to generate receipt PDF for payment id=%s", payment.id)
