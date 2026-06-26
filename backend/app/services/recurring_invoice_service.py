import calendar
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.models import Invoice, RecurringInvoice
from app.services.activity import log_invoice_activity

logger = logging.getLogger(__name__)


def calculate_next_due_date(r: RecurringInvoice, from_date: date) -> date:
    if r.frequency == "daily":
        next_date = from_date + relativedelta(days=r.frequency_interval)
    elif r.frequency == "weekly":
        next_date = from_date + relativedelta(weeks=r.frequency_interval)
    elif r.frequency == "monthly":
        next_date = from_date + relativedelta(months=r.frequency_interval)
        if r.day_of_month:
            max_day = calendar.monthrange(next_date.year, next_date.month)[1]
            next_date = next_date.replace(day=min(r.day_of_month, max_day))
    elif r.frequency == "yearly":
        next_date = from_date + relativedelta(years=r.frequency_interval)
    else:
        next_date = from_date + relativedelta(months=r.frequency_interval)
    return next_date


def _is_exhausted(r: RecurringInvoice) -> bool:
    if r.end_date and r.next_due_date > r.end_date:
        return True
    if r.max_occurrences and r.occurrence_count >= r.max_occurrences:
        return True
    return False


def _generate_one(db: Session, r: RecurringInvoice) -> Invoice:
    r.occurrence_count += 1
    invoice_number = f"{r.invoice_number_base}-{r.occurrence_count}"

    net_amount = r.net_amount
    if net_amount is None and r.vat_amount is not None:
        net_amount = r.gross_amount - r.vat_amount

    invoice = Invoice(
        file_id=None,
        supplier_name_raw=r.supplier_name_raw,
        paying_entity_raw=r.paying_entity_raw,
        paying_entity_id=r.paying_entity_id,
        project_id=r.project_id,
        invoice_number=invoice_number,
        invoice_date=r.next_due_date,
        gross_amount=r.gross_amount,
        vat_amount=r.vat_amount,
        net_amount=net_amount,
        currency=r.currency,
        description=r.description,
        ocr_status="manual",
        extraction_status="manual",
        review_status="auto_accepted",
        is_approved_to_pay=False,
        is_legacy=False,
    )
    db.add(invoice)
    db.flush()

    log_invoice_activity(
        db=db,
        event_type="invoice_created_recurring",
        event_label=f"Recurring invoice generated (occurrence {r.occurrence_count})",
        invoice_id=invoice.id,
        project_id=invoice.project_id,
        entity_id=invoice.paying_entity_id,
        changed_by=None,
        new_values={
            "supplier_name_raw": r.supplier_name_raw,
            "invoice_number": invoice_number,
            "gross_amount": str(r.gross_amount),
            "invoice_date": r.next_due_date.isoformat(),
            "recurring_invoice_id": r.id,
            "occurrence": r.occurrence_count,
        },
    )

    r.last_generated_at = datetime.now(timezone.utc)
    r.next_due_date = calculate_next_due_date(r, r.next_due_date)
    if _is_exhausted(r):
        r.is_active = False

    return invoice


def process_due_recurring_invoices(db: Session) -> int:
    today = date.today()
    due = (
        db.query(RecurringInvoice)
        .filter(RecurringInvoice.is_active.is_(True), RecurringInvoice.next_due_date <= today)
        .all()
    )

    generated = 0
    for r in due:
        try:
            if _is_exhausted(r):
                r.is_active = False
                continue
            _generate_one(db, r)
            generated += 1
        except Exception:
            logger.exception("Failed to generate recurring invoice id=%s", r.id)

    if generated or due:
        db.commit()

    logger.info("Recurring invoice job: checked=%d generated=%d", len(due), generated)
    return generated


def create_recurring_invoice(db: Session, data, created_by: int) -> RecurringInvoice:
    net_amount = data.net_amount
    if net_amount is None and data.vat_amount is not None:
        net_amount = data.gross_amount - data.vat_amount

    # First due date: start_date, adjusted for day_of_month if monthly
    first_due = data.start_date
    if data.frequency == "monthly" and data.day_of_month:
        max_day = calendar.monthrange(first_due.year, first_due.month)[1]
        first_due = first_due.replace(day=min(data.day_of_month, max_day))

    r = RecurringInvoice(
        supplier_name_raw=data.supplier_name_raw,
        paying_entity_raw=data.paying_entity_raw,
        paying_entity_id=data.paying_entity_id,
        project_id=data.project_id,
        invoice_number_base=data.invoice_number_base,
        gross_amount=data.gross_amount,
        vat_amount=data.vat_amount,
        net_amount=net_amount,
        currency=data.currency,
        description=data.description,
        frequency=data.frequency,
        frequency_interval=data.frequency_interval,
        day_of_month=data.day_of_month,
        start_date=data.start_date,
        end_date=data.end_date,
        max_occurrences=data.max_occurrences,
        occurrence_count=0,
        next_due_date=first_due,
        is_active=True,
        created_by=created_by,
    )
    db.add(r)
    db.flush()

    # If first due date is today or in the past, generate the first invoice immediately
    if first_due <= date.today():
        _generate_one(db, r)

    db.commit()
    db.refresh(r)
    return r
