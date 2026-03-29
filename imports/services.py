from decimal import Decimal, InvalidOperation

import pandas as pd
from django.utils import timezone

from core.models import Unit
from billing.models import Charge


def _norm(s: str) -> str:
    return str(s).strip().lower()


def process_excel_upload(upload, *, year_override=None, month_override=None):
    """
    يدعم حالياً LONG format:
    - كل صف = مديونية واحدة
    """
    source = upload.source
    mapping = source.mapping or {}

    sheet_name = mapping.get("sheet_name", 0)

    df = pd.read_excel(upload.file.path, sheet_name=sheet_name, dtype=object)
    # normalize dataframe columns
    df.columns = [_norm(c) for c in df.columns]

    def col(name):
        return _norm(name)

    created = 0
    skipped = 0
    errors = []

    if source.format_type == "LONG":
        unit_key_col = mapping.get("unit_key_col", "unit_key")
        year_col = mapping.get("year_col", "year")
        month_col = mapping.get("month_col", "month")         # optional
        type_col = mapping.get("type_col", "type")
        amount_col = mapping.get("amount_col", "amount")
        notes_col = mapping.get("notes_col", "notes")         # optional

        # optional: map values to system types
        # مثال:
        # "type_map": {"كهرباء": "ELECTRICITY", "مياه": "WATER"}
        type_map = mapping.get("type_map", {})

        required = [col(unit_key_col), col(type_col), col(amount_col)]
        if year_override is None:
            required.append(col(year_col))
        for r in required:
            if r not in df.columns:
                raise ValueError(f"Missing required column: {r}")

        for i, row in df.iterrows():
            # Excel row number (header is row 1)
            excel_row_number = int(i) + 2

            try:
                unit_key = str(row[col(unit_key_col)]).strip()
                if not unit_key or unit_key.lower() == "nan":
                    raise ValueError("unit_key empty")

                try:
                    unit = Unit.objects.get(resort=upload.resort, unit_key=unit_key)
                except Unit.DoesNotExist:
                    raise ValueError(f"Unit not found: {unit_key}")

                if year_override is not None and str(year_override).strip() != "":
                    year = int(year_override)
                else:
                    year = int(row[col(year_col)])

                month_val = None
                if month_override is not None:
                    month_val = int(month_override) if str(month_override).strip() != "" else None
                elif month_col and col(month_col) in df.columns:
                    mv = row[col(month_col)]
                    if mv is not None and str(mv).strip().lower() not in ("", "nan"):
                        month_val = int(mv)

                raw_type = str(row[col(type_col)]).strip()
                if not raw_type or raw_type.lower() == "nan":
                    raise ValueError("type empty")

                # apply type_map if provided
                mapped_type = type_map.get(raw_type, raw_type)
                ctype = str(mapped_type).strip().upper()

                allowed_types = {t for t, _ in Charge.Type.choices}
                if ctype not in allowed_types:
                    raise ValueError(f"Invalid type: {ctype}")

                raw_amount = row[col(amount_col)]
                try:
                    amount = Decimal(str(raw_amount))
                except (InvalidOperation, TypeError):
                    raise ValueError(f"Invalid amount: {raw_amount}")

                notes = ""
                if notes_col and col(notes_col) in df.columns:
                    nv = row[col(notes_col)]
                    if nv is not None and str(nv).strip().lower() != "nan":
                        notes = str(nv).strip()

                obj, was_created = Charge.objects.get_or_create(
                    source_upload=upload,
                    source_row=excel_row_number,
                    type=ctype,
                    defaults=dict(
                        resort=upload.resort,
                        unit=unit,
                        year=year,
                        month=month_val,
                        amount=amount,
                        notes=notes,
                        status=Charge.Status.PENDING,
                    ),
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

            except Exception as e:
                errors.append(f"Row {excel_row_number}: {e}")

    elif source.format_type == "WIDE":
        unit_key_col = mapping.get("unit_key_col", "unit_key")
        year_col = mapping.get("year_col")
        month_col = mapping.get("month_col")

        # mapping example:
        # {
        #   "charges_map": {"electricity": "ELECTRICITY", "water": "WATER"},
        #   "unit_key_col": "unit_key"
        # }
        charges_map = mapping.get("charges_map") or {}
        if not charges_map:
            raise ValueError("WIDE format requires mapping.charges_map")

        if col(unit_key_col) not in df.columns:
            raise ValueError(f"Missing required column: {col(unit_key_col)}")

        allowed_types = {t for t, _ in Charge.Type.choices}

        for i, row in df.iterrows():
            excel_row_number = int(i) + 2
            try:
                unit_key = str(row[col(unit_key_col)]).strip()
                if not unit_key or unit_key.lower() == "nan":
                    raise ValueError("unit_key empty")

                try:
                    unit = Unit.objects.get(resort=upload.resort, unit_key=unit_key)
                except Unit.DoesNotExist:
                    raise ValueError(f"Unit not found: {unit_key}")

                if year_override is not None and str(year_override).strip() != "":
                    year = int(year_override)
                elif year_col and col(year_col) in df.columns:
                    year = int(row[col(year_col)])
                else:
                    raise ValueError("year is required for WIDE format (provide year_override or year_col)")

                month_val = None
                if month_override is not None:
                    month_val = int(month_override) if str(month_override).strip() != "" else None
                elif month_col and col(month_col) in df.columns:
                    mv = row[col(month_col)]
                    if mv is not None and str(mv).strip().lower() not in ("", "nan"):
                        month_val = int(mv)

                for amount_col_name, charge_type in charges_map.items():
                    if col(amount_col_name) not in df.columns:
                        continue

                    ctype = str(charge_type).strip().upper()
                    if ctype not in allowed_types:
                        raise ValueError(f"Invalid type in charges_map: {ctype}")

                    raw_amount = row[col(amount_col_name)]
                    if raw_amount is None or str(raw_amount).strip().lower() in ("", "nan"):
                        continue
                    try:
                        amount = Decimal(str(raw_amount))
                    except (InvalidOperation, TypeError):
                        raise ValueError(f"Invalid amount in column {amount_col_name}: {raw_amount}")

                    if amount <= 0:
                        continue

                    obj, was_created = Charge.objects.get_or_create(
                        source_upload=upload,
                        source_row=excel_row_number,
                        type=ctype,
                        defaults=dict(
                            resort=upload.resort,
                            unit=unit,
                            year=year,
                            month=month_val,
                            amount=amount,
                            notes="",
                            status=Charge.Status.PENDING,
                        ),
                    )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1

            except Exception as e:
                errors.append(f"Row {excel_row_number}: {e}")

    else:
        raise ValueError(f"Unsupported format_type: {source.format_type}")

    upload.processed_at = timezone.now()
    if errors:
        upload.status = "FAILED"
        upload.error = "\n".join(errors[:300])  # limit
    else:
        upload.status = "PROCESSED"
        upload.error = f"created={created}, skipped={skipped}"

    upload.save(update_fields=["processed_at", "status", "error"])
    return {"created": created, "skipped": skipped, "errors": errors}