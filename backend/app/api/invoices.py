from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Invoice

router = APIRouter(prefix="/invoices", tags=["Invoices"])

@router.get("/")
def get_invoices(
    db: Session = Depends(get_db),
    is_paid: bool = None,
    is_approved_to_pay: bool = None,
    is_vat_recovered: bool = None,
    review_status: str = None
):
    query = db.query(Invoice)
    
    if is_paid is not None:
        query = query.filter(Invoice.is_paid == is_paid)
    if is_approved_to_pay is not None:
        query = query.filter(Invoice.is_approved_to_pay == is_approved_to_pay)
    if is_vat_recovered is not None:
        query = query.filter(Invoice.is_vat_recovered == is_vat_recovered)
    if review_status:
        query = query.filter(Invoice.review_status == review_status)
    
    return query.all()

@router.get("/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.patch("/{invoice_id}/status")
def update_invoice_status(
    invoice_id: int,
    is_paid: bool = None,
    is_approved_to_pay: bool = None,
    is_vat_recovered: bool = None,
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if is_paid is not None:
        invoice.is_paid = is_paid
    if is_approved_to_pay is not None:
        invoice.is_approved_to_pay = is_approved_to_pay
    if is_vat_recovered is not None:
        invoice.is_vat_recovered = is_vat_recovered
    
    db.commit()
    db.refresh(invoice)
    return invoice