import logging

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

logger = logging.getLogger("billing.receipts")


def generate_clearance_pdf(statement, charges):
    """
    Renders and stores a clearance statement's PDF. Unlike a payment
    receipt, a clearance statement can legitimately be regenerated at a
    later as_of_date — but each individual statement row, once created,
    is never re-rendered or mutated.

    Best-effort: logs and returns on any failure rather than raising, since
    a PDF-rendering bug must never break the statement record itself.
    """
    try:
        import weasyprint
        from users.models import User

        unit = statement.unit
        owner_unit = (
            unit.owner_units.filter(owner__role=User.Role.OWNER)
            .select_related("owner")
            .first()
        )
        if owner_unit and owner_unit.owner.fullname:
            owner_name = owner_unit.owner.fullname
        elif owner_unit:
            owner_name = owner_unit.owner.phone
        else:
            owner_name = ""

        requester = statement.requested_by
        requester_name = requester.fullname or requester.phone

        html = render_to_string(
            "billing/clearance.html",
            {
                "statement": statement,
                "unit": unit,
                "resort": unit.resort,
                "owner_name": owner_name,
                "requester_name": requester_name,
                "charges": charges,
            },
        )
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        statement.pdf.save(f"clearance-{statement.id}.pdf", ContentFile(pdf_bytes), save=True)
    except Exception:
        logger.exception("Failed to generate clearance PDF for statement id=%s", statement.id)
