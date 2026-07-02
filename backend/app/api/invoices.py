import hashlib
import os
from decimal import Decimal, InvalidOperation
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.deps import current_user
from app.core.permissions import require_permission, has_permission, Permission
from app.models.models import Invoice, InvoiceFile, InvoiceActivityLog, User
from app.schemas.invoice import InvoiceResponse, InvoiceStatusUpdate, ManualInvoiceCreate
from app.services.activity import log_invoice_activity
from app.services.entity_extraction import extract_entity_from_text
from app.services.extraction import extract_invoice

router = APIRouter(prefix="/invoices", tags=["Invoices"])

STORAGE_PATH = "storage/invoices"
os.makedirs(STORAGE_PATH, exist_ok=True)

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg"}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def clean_entity(name: str) -> Optional[str]:
    if not name:
        return None
    return name.strip()


def parse_amount(val):
    if val is None:
        return None
    try:
        cleaned = str(val).replace("£", "").replace(",", "").strip()
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_date(val) -> Optional[date]:
    """Parse a date value from string (YYYY-MM-DD), date, or datetime."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        cleaned = str(val).strip()
        if not cleaned:
            return None
        return date.fromisoformat(cleaned[:10])
    except (ValueError, TypeError):
        return None


@router.get("/", response_model=List[InvoiceResponse])
def get_invoices(
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
    is_paid: Optional[bool] = None,
    is_approved_to_pay: Optional[bool] = None,
    is_vat_recovered: Optional[bool] = None,
    review_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
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

    return (
        query.order_by(Invoice.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/upload", response_model=InvoiceResponse)
def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    try:
        contents = file.file.read()

        if not contents:
            raise HTTPException(status_code=400, detail="Empty file")

        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum 20MB.",
            )

        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        original_name = os.path.basename(file.filename or "uploaded_file")
        extension = os.path.splitext(original_name)[1].lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file extension")

        file_hash = hashlib.sha256(contents).hexdigest()

        existing = db.query(InvoiceFile).filter(
            InvoiceFile.file_hash == file_hash
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Duplicate invoice file")

        stored_filename = f"{file_hash}{extension}"
        stored_path = os.path.join(STORAGE_PATH, stored_filename)

        with open(stored_path, "wb") as f:
            f.write(contents)

        invoice_file = InvoiceFile(
            original_filename=original_name,
            stored_path=stored_path,
            file_hash=file_hash,
            mime_type=file.content_type,
        )
        db.add(invoice_file)
        db.flush()

        invoice = Invoice(
            file_id=invoice_file.id,
            ocr_status="pending",
            extraction_status="pending",
            review_status="pending",
        )
        db.add(invoice)
        db.flush()

        log_invoice_activity(
            db=db,
            event_type="invoice_uploaded",
            event_label="Invoice uploaded",
            invoice_id=invoice.id,
            project_id=invoice.project_id,
            entity_id=invoice.paying_entity_id,
            changed_by=actor.id,
            new_values={
                "original_filename": original_name,
                "file_id": invoice_file.id,
            },
        )

        db.commit()
        db.refresh(invoice)

        return invoice

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Upload failed")


@router.post("/upload-batch")
def upload_invoices_batch(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    uploaded = []
    failed = []

    for file in files:
        try:
            contents = file.file.read()

            if not contents:
                failed.append({
                    "file_name": file.filename,
                    "error": "Empty file",
                })
                continue

            if len(contents) > MAX_FILE_SIZE:
                failed.append({
                    "file_name": file.filename,
                    "error": "File too large. Maximum 20MB.",
                })
                continue

            if file.content_type not in ALLOWED_TYPES:
                failed.append({
                    "file_name": file.filename,
                    "error": "Unsupported file type",
                })
                continue

            original_name = os.path.basename(file.filename or "uploaded_file")
            extension = os.path.splitext(original_name)[1].lower()

            if extension not in ALLOWED_EXTENSIONS:
                failed.append({
                    "file_name": original_name,
                    "error": "Unsupported file extension",
                })
                continue

            file_hash = hashlib.sha256(contents).hexdigest()

            existing = db.query(InvoiceFile).filter(
                InvoiceFile.file_hash == file_hash
            ).first()

            if existing:
                failed.append({
                    "file_name": original_name,
                    "error": "Duplicate invoice file",
                })
                continue

            stored_filename = f"{file_hash}{extension}"
            stored_path = os.path.join(STORAGE_PATH, stored_filename)

            with open(stored_path, "wb") as f:
                f.write(contents)

            invoice_file = InvoiceFile(
                original_filename=original_name,
                stored_path=stored_path,
                file_hash=file_hash,
                mime_type=file.content_type,
            )
            db.add(invoice_file)
            db.flush()

            invoice = Invoice(
                file_id=invoice_file.id,
                ocr_status="pending",
                extraction_status="pending",
                review_status="pending",
            )
            db.add(invoice)
            db.flush()

            log_invoice_activity(
                db=db,
                event_type="invoice_uploaded",
                event_label="Invoice uploaded",
                invoice_id=invoice.id,
                project_id=invoice.project_id,
                entity_id=invoice.paying_entity_id,
                changed_by=actor.id,
                new_values={
                    "original_filename": original_name,
                    "file_id": invoice_file.id,
                },
            )

            db.commit()
            db.refresh(invoice)

            uploaded.append({
                "file_name": original_name,
                "invoice_id": invoice.id,
                "status": "uploaded",
            })

        except Exception as e:
            db.rollback()
            failed.append({
                "file_name": getattr(file, "filename", "unknown"),
                "error": str(e),
            })

    return {
        "uploaded_count": len(uploaded),
        "failed_count": len(failed),
        "uploaded": uploaded,
        "failed": failed,
    }


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/file")
def get_invoice_file(
    invoice_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not invoice.file_id:
        raise HTTPException(status_code=404, detail="No file attached to this invoice")

    invoice_file = db.query(InvoiceFile).filter(InvoiceFile.id == invoice.file_id).first()
    if not invoice_file:
        raise HTTPException(status_code=404, detail="Invoice file not found")

    if not os.path.exists(invoice_file.stored_path):
        raise HTTPException(status_code=404, detail="Stored invoice file not found")

    return FileResponse(
        path=invoice_file.stored_path,
        media_type=invoice_file.mime_type or "application/octet-stream",
        filename=invoice_file.original_filename,
        headers={"Content-Disposition": f"inline; filename=\"{invoice_file.original_filename}\""},
    )


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    old_values = {
        "invoice_number": invoice.invoice_number,
        "supplier_name_raw": invoice.supplier_name_raw,
        "paying_entity_raw": invoice.paying_entity_raw,
        "paying_entity_id": invoice.paying_entity_id,
        "project_id": invoice.project_id,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "gross_amount": str(invoice.gross_amount) if invoice.gross_amount is not None else None,
        "vat_amount": str(invoice.vat_amount) if invoice.vat_amount is not None else None,
        "net_amount": str(invoice.net_amount) if invoice.net_amount is not None else None,
        "currency": invoice.currency,
        "review_status": invoice.review_status,
        "ocr_status": invoice.ocr_status,
        "extraction_status": invoice.extraction_status,
        "is_legacy": invoice.is_legacy,
    }

    allowed_fields = {
        "invoice_number",
        "supplier_name_raw",
        "paying_entity_raw",
        "paying_entity_id",
        "project_id",
        "invoice_date",
        "due_date",
        "gross_amount",
        "vat_amount",
        "net_amount",
        "currency",
        "review_status",
        "ocr_status",
        "extraction_status",
        "is_legacy",
    }

    date_fields = {"invoice_date", "due_date"}
    amount_fields = {"gross_amount", "vat_amount", "net_amount"}

    for key, value in data.items():
        if key not in allowed_fields:
            continue
        if key in amount_fields:
            setattr(invoice, key, parse_amount(value))
        elif key in date_fields:
            setattr(invoice, key, parse_date(value))
        else:
            setattr(invoice, key, value)

    db.flush()

    new_values = {
        "invoice_number": invoice.invoice_number,
        "supplier_name_raw": invoice.supplier_name_raw,
        "paying_entity_raw": invoice.paying_entity_raw,
        "paying_entity_id": invoice.paying_entity_id,
        "project_id": invoice.project_id,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "gross_amount": str(invoice.gross_amount) if invoice.gross_amount is not None else None,
        "vat_amount": str(invoice.vat_amount) if invoice.vat_amount is not None else None,
        "net_amount": str(invoice.net_amount) if invoice.net_amount is not None else None,
        "currency": invoice.currency,
        "review_status": invoice.review_status,
        "ocr_status": invoice.ocr_status,
        "extraction_status": invoice.extraction_status,
        "is_legacy": invoice.is_legacy,
    }

    log_invoice_activity(
        db=db,
        event_type="invoice_updated_manual",
        event_label="Invoice manually edited",
        invoice_id=invoice.id,
        project_id=invoice.project_id,
        entity_id=invoice.paying_entity_id,
        changed_by=actor.id,
        old_values=old_values,
        new_values=new_values,
    )

    db.commit()
    db.refresh(invoice)
    return invoice


@router.patch("/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(
    invoice_id: int,
    status: InvoiceStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    # Per-field permission checks — only check the perms the user is using
    if status.is_paid is not None and not has_permission(actor, Permission.TOGGLE_PAID):
        raise HTTPException(403, "You don't have permission to mark invoices as paid.")
    if status.is_vat_recovered is not None and not has_permission(actor, Permission.TOGGLE_VAT_RECOVERED):
        raise HTTPException(403, "You don't have permission to toggle VAT recovered.")
    if status.is_approved_to_pay is not None and not has_permission(actor, Permission.APPROVE_TO_PAY):
        raise HTTPException(403, "Only partners or admins can mark invoices as approved to pay.")
    if status.is_legacy is not None and not has_permission(actor, Permission.EDIT_INVOICE):
        raise HTTPException(403, "You don't have permission to toggle legacy.")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    old_values = {
        "is_paid": invoice.is_paid,
        "is_approved_to_pay": invoice.is_approved_to_pay,
        "is_vat_recovered": invoice.is_vat_recovered,
        "is_legacy": invoice.is_legacy,
    }

    if status.is_paid is not None:
        invoice.is_paid = status.is_paid

    if status.is_approved_to_pay is not None:
        invoice.is_approved_to_pay = status.is_approved_to_pay

    if status.is_vat_recovered is not None:
        invoice.is_vat_recovered = status.is_vat_recovered

    if status.is_legacy is not None:
        invoice.is_legacy = status.is_legacy

    db.flush()
    db.refresh(invoice)

    new_values = {
        "is_paid": invoice.is_paid,
        "is_approved_to_pay": invoice.is_approved_to_pay,
        "is_vat_recovered": invoice.is_vat_recovered,
        "is_legacy": invoice.is_legacy,
    }

    if old_values["is_approved_to_pay"] != new_values["is_approved_to_pay"] and new_values["is_approved_to_pay"]:
        log_invoice_activity(
            db=db,
            event_type="invoice_approved_to_pay",
            event_label="Invoice approved to pay",
            invoice_id=invoice.id,
            project_id=invoice.project_id,
            entity_id=invoice.paying_entity_id,
            changed_by=actor.id,
            old_values={"is_approved_to_pay": old_values["is_approved_to_pay"]},
            new_values={"is_approved_to_pay": new_values["is_approved_to_pay"]},
        )

    if old_values["is_paid"] != new_values["is_paid"] and new_values["is_paid"]:
        log_invoice_activity(
            db=db,
            event_type="invoice_paid",
            event_label="Invoice marked paid",
            invoice_id=invoice.id,
            project_id=invoice.project_id,
            entity_id=invoice.paying_entity_id,
            changed_by=actor.id,
            old_values={"is_paid": old_values["is_paid"]},
            new_values={"is_paid": new_values["is_paid"]},
        )

    if old_values["is_vat_recovered"] != new_values["is_vat_recovered"] and new_values["is_vat_recovered"]:
        log_invoice_activity(
            db=db,
            event_type="invoice_vat_recovered",
            event_label="VAT marked recovered",
            invoice_id=invoice.id,
            project_id=invoice.project_id,
            entity_id=invoice.paying_entity_id,
            changed_by=actor.id,
            old_values={"is_vat_recovered": old_values["is_vat_recovered"]},
            new_values={"is_vat_recovered": new_values["is_vat_recovered"]},
        )

    if old_values["is_legacy"] != new_values["is_legacy"]:
        log_invoice_activity(
            db=db,
            event_type="invoice_legacy_toggled",
            event_label=f"Marked legacy: {new_values['is_legacy']}",
            invoice_id=invoice.id,
            project_id=invoice.project_id,
            entity_id=invoice.paying_entity_id,
            changed_by=actor.id,
            old_values={"is_legacy": old_values["is_legacy"]},
            new_values={"is_legacy": new_values["is_legacy"]},
        )

    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/{invoice_id}")
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.DELETE_INVOICE)),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    old_values = {
        "invoice_number": invoice.invoice_number,
        "supplier_name_raw": invoice.supplier_name_raw,
        "paying_entity_id": invoice.paying_entity_id,
        "project_id": invoice.project_id,
        "gross_amount": str(invoice.gross_amount) if invoice.gross_amount is not None else None,
    }

    invoice_file = None
    if invoice.file_id:
        invoice_file = db.query(InvoiceFile).filter(InvoiceFile.id == invoice.file_id).first()

    stored_path = invoice_file.stored_path if invoice_file else None

    try:
        # Detach all historical activity rows from this invoice before deleting it,
        # otherwise the foreign key constraint blocks the delete.
        db.query(InvoiceActivityLog).filter(
            InvoiceActivityLog.invoice_id == invoice.id
        ).update(
            {InvoiceActivityLog.invoice_id: None},
            synchronize_session=False,
        )

        log_invoice_activity(
            db=db,
            event_type="invoice_deleted",
            event_label="Invoice deleted",
            invoice_id=None,
            project_id=invoice.project_id,
            entity_id=invoice.paying_entity_id,
            changed_by=actor.id,
            old_values={
                **old_values,
                "deleted_invoice_id": invoice.id,
            },
        )

        db.delete(invoice)
        if invoice_file:
            db.delete(invoice_file)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete invoice: {str(e)}")

    if stored_path and os.path.exists(stored_path):
        try:
            os.remove(stored_path)
        except OSError:
            pass

    return {"message": "Invoice deleted successfully"}


@router.post("/{invoice_id}/extract")
def trigger_extraction(
    invoice_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
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

        paying_entity = fields.get("paying_entity_raw")
        entity_source = "azure"
        entity_confidence = None

        if not paying_entity or not str(paying_entity).strip():
            if result.get("raw_text"):
                claude_result = extract_entity_from_text(result["raw_text"])
                entity = claude_result.get("entity")

                if (
                    claude_result.get("confidence") in ["high", "medium"]
                    and entity
                    and isinstance(entity, str)
                ):
                    paying_entity = clean_entity(entity)
                    entity_source = "llm"
                    entity_confidence = claude_result.get("confidence")

        invoice.paying_entity_raw = str(paying_entity or "")
        invoice.invoice_number = str(fields.get("invoice_number") or "")

        invoice_date = fields.get("invoice_date")
        if invoice_date:
            try:
                invoice.invoice_date = (
                    invoice_date.date()
                    if hasattr(invoice_date, "date")
                    else invoice_date
                )
            except (ValueError, TypeError, AttributeError):
                pass

        due_date = fields.get("due_date")
        if due_date:
            try:
                invoice.due_date = (
                    due_date.date()
                    if hasattr(due_date, "date")
                    else due_date
                )
            except (ValueError, TypeError, AttributeError):
                pass

        invoice.gross_amount = parse_amount(fields.get("gross_amount"))
        invoice.vat_amount = parse_amount(fields.get("vat_amount"))
        invoice.net_amount = parse_amount(fields.get("net_amount"))

        # Resolve currency from Azure CurrencyValue (code takes priority over symbol)
        SYMBOL_TO_CODE = {
            "£": "GBP", "€": "EUR", "$": "USD",
            "﷼": "SAR", "د.إ": "AED", "LL": "LBP", "LBP": "LBP",
            "CHF": "CHF", "Fr": "CHF",
        }
        raw_code = (fields.get("currency_code") or "").strip().upper()
        raw_symbol = (fields.get("currency_symbol") or "").strip()
        resolved_currency = (
            raw_code if raw_code in SYMBOL_TO_CODE.values()
            else SYMBOL_TO_CODE.get(raw_symbol)
            or SYMBOL_TO_CODE.get(raw_code)
        )
        if resolved_currency:
            invoice.currency = resolved_currency

        key_fields_present = (
            bool(invoice.supplier_name_raw)
            and bool(invoice.invoice_number)
            and invoice.gross_amount is not None
        )

        invoice.review_status = (
            "auto_accepted" if key_fields_present else "needs_review"
        )
        invoice.ocr_status = "completed"
        invoice.extraction_status = "completed"

        db.commit()
        db.refresh(invoice)

        return {
            "invoice_id": invoice_id,
            "status": "extraction_complete",
            "review_status": invoice.review_status,
            "entity_source": entity_source,
            "entity_confidence": entity_confidence,
            "extracted_fields": fields,
            "confidence_scores": confidence,
            "line_items": result.get("line_items", []),
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


@router.post("/manual", response_model=InvoiceResponse)
def create_manual_invoice(
    invoice_data: ManualInvoiceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    try:
        # Auto-calculate net_amount if not provided and vat_amount is provided
        net_amount = invoice_data.net_amount
        if net_amount is None and invoice_data.vat_amount is not None:
            net_amount = invoice_data.gross_amount - invoice_data.vat_amount

        invoice = Invoice(
            file_id=None,
            supplier_name_raw=invoice_data.supplier_name_raw,
            paying_entity_raw=invoice_data.paying_entity_raw,
            paying_entity_id=invoice_data.paying_entity_id,
            project_id=invoice_data.project_id,
            invoice_number=invoice_data.invoice_number,
            invoice_date=invoice_data.invoice_date,
            due_date=invoice_data.due_date,
            description=invoice_data.description,
            gross_amount=invoice_data.gross_amount,
            vat_amount=invoice_data.vat_amount,
            net_amount=net_amount,
            currency=invoice_data.currency,
            ocr_status="manual",
            extraction_status="manual",
            review_status="auto_accepted",
            is_legacy=False,
        )
        db.add(invoice)
        db.flush()

        log_invoice_activity(
            db=db,
            event_type="invoice_created_manual",
            event_label="Invoice created manually",
            invoice_id=invoice.id,
            project_id=invoice.project_id,
            entity_id=invoice.paying_entity_id,
            changed_by=actor.id,
            new_values={
                "supplier_name_raw": invoice_data.supplier_name_raw,
                "invoice_number": invoice_data.invoice_number,
                "gross_amount": str(invoice_data.gross_amount),
                "invoice_date": invoice_data.invoice_date.isoformat(),
                "paying_entity_raw": invoice_data.paying_entity_raw,
                "paying_entity_id": invoice_data.paying_entity_id,
                "project_id": invoice_data.project_id,
                "vat_amount": str(invoice_data.vat_amount) if invoice_data.vat_amount is not None else None,
                "net_amount": str(net_amount) if net_amount is not None else None,
                "due_date": invoice_data.due_date.isoformat() if invoice_data.due_date else None,
                "description": invoice_data.description,
                "currency": invoice_data.currency,
            },
        )

        db.commit()
        db.refresh(invoice)

        return invoice

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create manual invoice: {str(e)}")


# ── Credit note links for an invoice ─────────────────────────────────────────

@router.get("/{invoice_id}/credit-note-links")
def get_invoice_credit_note_links(
    invoice_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    from app.models.models import CreditNote, CreditNoteLink
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    links = (
        db.query(CreditNoteLink, CreditNote)
        .join(CreditNote, CreditNote.id == CreditNoteLink.credit_note_id)
        .filter(CreditNoteLink.invoice_id == invoice_id)
        .all()
    )

    result = []
    for link, cn in links:
        result.append({
            "link_id": link.id,
            "credit_note_id": cn.id,
            "credit_number": cn.credit_number,
            "supplier_name_raw": cn.supplier_name_raw,
            "gross_amount": str(cn.gross_amount) if cn.gross_amount is not None else None,
            "allocated_amount": str(link.allocated_amount) if link.allocated_amount is not None else None,
            "file_id": cn.file_id,
            "is_paid": cn.is_paid,
            "is_approved_to_pay": cn.is_approved_to_pay,
        })
    return result
    