import logging

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

logger = logging.getLogger("collections_app.receipts")


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
        from users.models import User

        owner_unit = (
            payment.unit.owner_units.filter(owner__role=User.Role.OWNER)
            .select_related("owner")
            .first()
        )
        if owner_unit and owner_unit.owner.fullname:
            owner_name = owner_unit.owner.fullname
        elif owner_unit:
            owner_name = owner_unit.owner.phone
        else:
            owner_name = ""

        is_online = payment.receipt_no.startswith("ONLINE-")

        html = render_to_string(
            "collections_app/receipt.html",
            {
                "payment": payment,
                "unit": payment.unit,
                "resort": payment.resort,
                "owner_name": owner_name,
                "allocations": payment.allocations.select_related("charge").all(),
                "channel_label": "دفع أونلاين" if is_online else "دفع نقدي / تحويل",
            },
        )
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        payment.receipt_pdf.save(f"receipt-{payment.id}.pdf", ContentFile(pdf_bytes), save=True)
    except Exception:
        logger.exception("Failed to generate receipt PDF for payment id=%s", payment.id)
