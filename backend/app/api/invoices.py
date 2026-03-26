from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal, InvalidOperation
import hashlib
import os
from app.db.database import get_db
from app.models.models import Invoice, InvoiceFile
from app.schemas.invoice import InvoiceResponse, InvoiceStatusUpdate
from app.services.extraction import extract_invoice

router = APIRouter(prefix="/invoices", tags=["Invoices"])

STORAGE_PATH = "storage/invoices"
os.makedirs(STORAGE_PATH, exist_ok=True)

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg"}


@router.get("/", response_model=List[InvoiceResponse])
def get_invoices(
    db: Session = Depends(get_db),
    is_paid: Optional[bool] = None,
    is_approved_to_pay: Optional[bool] = None,
    is_vat_recovered: Optional[bool] = None,
    review_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
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
    return query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/upload", response_model=InvoiceResponse)
def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        contents = file.file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file")

        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # SHA-256 for safer deduplication
        file_hash = hashlib.sha256(contents).hexdigest()

        existing = db.query(InvoiceFile).filter(
            InvoiceFile.file_hash == file_hash
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Duplicate invoice file")

        # Sanitise filename
        original_name = os.path.basename(file.filename or "uploaded_file")
        extension = os.path.splitext(original_name)[1].lower()
        stored_filename = f"{file_hash}{extension}"
        stored_path = os.path.join(STORAGE_PATH, stored_filename)

        with open(stored_path, "wb") as f:
            f.write(contents)

        invoice_file = InvoiceFile(
            original_filename=original_name,
            stored_path=stored_path,
            file_hash=file_hash,
            mime_type=file.content_type
        )
        db.add(invoice_file)
        db.flush()  # gets invoice_file.id without full commit

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

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Upload failed")


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


@router.post("/{invoice_id}/extract")
def trigger_extraction(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice_file = db.query(InvoiceFile).filter(
        InvoiceFile.id == invoice.file_id
    ).first()
    if not invoice_file:
        raise HTTPException(status_code=404, detail="Invoice file not found")

    try:
        invoice.ocr_status = "processing"
        db.commit()

        result = extract_invoice(invoice_file.stored_path)

        if result["status"] == "no_document_extracted":
            invoice.ocr_status = "failed"
            invoice.extraction_status = "failed"
            invoice.review_status = "needs_review"
            db.commit()
            raise HTTPException(status_code=422, detail="No document extracted")

        fields = result["extracted_fields"]
        confidence = result["confidence_scores"]

        invoice.supplier_name_raw = str(fields.get("supplier_name_raw") or "")
        invoice.paying_entity_raw = str(fields.get("paying_entity_raw") or "")
        invoice.invoice_number = str(fields.get("invoice_number") or "")

        # Handle dates safely
        invoice_date = fields.get("invoice_date")
        if invoice_date:
            try:
                invoice.invoice_date = invoice_date.date() if hasattr(
                    invoice_date, "date"
                ) else invoice_date
            except (ValueError, TypeError, AttributeError):
                pass

        due_date = fields.get("due_date")
        if due_date:
            try:
                invoice.due_date = due_date.date() if hasattr(
                    due_date, "date"
                ) else due_date
            except (ValueError, TypeError, AttributeError):
                pass

        # Use Decimal for money fields
        def parse_amount(val):
            if val is None:
                return None
            try:
                cleaned = str(val).replace("£", "").replace(",", "").strip()
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return None

        invoice.gross_amount = parse_amount(fields.get("gross_amount"))
        invoice.vat_amount = parse_amount(fields.get("vat_amount"))
        invoice.net_amount = parse_amount(fields.get("net_amount"))

        # Only auto-accept if key fields extracted successfully
        key_fields_present = all([
            invoice.supplier_name_raw,
            invoice.invoice_number,
            invoice.gross_amount
        ])
        invoice.review_status = "auto_accepted" if key_fields_present else "needs_review"
        invoice.ocr_status = "completed"
        invoice.extraction_status = "completed"

        db.commit()
        db.refresh(invoice)

        return {
            "invoice_id": invoice_id,
            "status": "extraction_complete",
            "review_status": invoice.review_status,
            "extracted_fields": fields,
            "confidence_scores": confidence,
            "line_items": result["line_items"]
        }

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            invoice.ocr_status = "failed"
            invoice.extraction_status = "failed"
            invoice.review_status = "needs_review"
            db.commit()
        raise HTTPException(status_code=500, detail="Extraction failed")