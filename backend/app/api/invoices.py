from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import hashlib
import shutil
import os
from app.db.database import get_db
from app.models.models import Invoice, InvoiceFile
from app.schemas.invoice import InvoiceResponse, InvoiceStatusUpdate

router = APIRouter(prefix="/invoices", tags=["Invoices"])

STORAGE_PATH = "storage/invoices"
os.makedirs(STORAGE_PATH, exist_ok=True)

@router.get("/", response_model=List[InvoiceResponse])
def get_invoices(
    db: Session = Depends(get_db),
    is_paid: Optional[bool] = None,
    is_approved_to_pay: Optional[bool] = None,
    is_vat_recovered: Optional[bool] = None,
    review_status: Optional[str] = None
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

@router.post("/upload", response_model=InvoiceResponse)
def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Read file and compute hash
    contents = file.file.read()
    file_hash = hashlib.md5(contents).hexdigest()

    # Check for duplicate
    existing = db.query(InvoiceFile).filter(
        InvoiceFile.file_hash == file_hash
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate invoice file")

    # Save file to storage
    stored_filename = f"{file_hash}_{file.filename}"
    stored_path = os.path.join(STORAGE_PATH, stored_filename)
    with open(stored_path, "wb") as f:
        f.write(contents)

    # Create invoice file record
    invoice_file = InvoiceFile(
        original_filename=file.filename,
        stored_path=stored_path,
        file_hash=file_hash,
        mime_type=file.content_type
    )
    db.add(invoice_file)
    db.commit()
    db.refresh(invoice_file)

    # Create invoice record
    invoice = Invoice(
        file_id=invoice_file.id,
        ocr_status="pending",
        extraction_status="pending",
        review_status="pending"
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice

@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.patch("/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(
    invoice_id: int,
    status: InvoiceStatusUpdate,
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if status.is_paid is not None:
        invoice.is_paid = status.is_paid
    if status.is_approved_to_pay is not None:
        invoice.is_approved_to_pay = status.is_approved_to_pay
    if status.is_vat_recovered is not None:
        invoice.is_vat_recovered = status.is_vat_recovered
    db.commit()
    db.refresh(invoice)
    return invoice