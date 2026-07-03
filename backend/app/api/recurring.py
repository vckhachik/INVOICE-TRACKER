from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.permissions import require_permission, Permission
from app.models.models import RecurringInvoice, User
from app.schemas.recurring_invoice import (
    RecurringInvoiceCreate,
    RecurringInvoiceUpdate,
    RecurringInvoiceResponse,
)
from app.services.recurring_invoice_service import (
    create_recurring_invoice,
    process_due_recurring_invoices,
)

router = APIRouter(prefix="/invoices/recurring", tags=["Recurring Invoices"])


@router.post("", response_model=RecurringInvoiceResponse)
def create(
    body: RecurringInvoiceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    try:
        return create_recurring_invoice(db, body, created_by=actor.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[RecurringInvoiceResponse])
def list_all(
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    q = db.query(RecurringInvoice)
    if active_only:
        q = q.filter(RecurringInvoice.is_active.is_(True))
    return q.order_by(RecurringInvoice.next_due_date).all()


@router.patch("/{recurring_id}", response_model=RecurringInvoiceResponse)
def update(
    recurring_id: int,
    body: RecurringInvoiceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    r = db.query(RecurringInvoice).filter(RecurringInvoice.id == recurring_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")

    if body.supplier_name_raw is not None:
        r.supplier_name_raw = body.supplier_name_raw
    if body.invoice_number_base is not None:
        r.invoice_number_base = body.invoice_number_base
    if body.gross_amount is not None:
        r.gross_amount = body.gross_amount
    if body.currency is not None:
        r.currency = body.currency.upper()
    if body.frequency is not None:
        r.frequency = body.frequency
    if body.frequency_interval is not None:
        r.frequency_interval = body.frequency_interval
    if body.day_of_month is not None:
        r.day_of_month = body.day_of_month
    if body.end_date is not None:
        r.end_date = body.end_date
    if body.max_occurrences is not None:
        r.max_occurrences = body.max_occurrences
    if body.is_active is not None:
        r.is_active = body.is_active
    if body.description is not None:
        r.description = body.description

    db.commit()
    db.refresh(r)
    return r


@router.delete("/{recurring_id}")
def delete(
    recurring_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    r = db.query(RecurringInvoice).filter(RecurringInvoice.id == recurring_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.post("/process")
def manual_process(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    generated = process_due_recurring_invoices(db)
    return {"ok": True, "generated": generated}
