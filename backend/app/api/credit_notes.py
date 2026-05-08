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
from app.models.models import CreditNote, CreditNoteLink, InvoiceFile, InvoiceActivityLog, User
from app.schemas.credit_note import (
    CreditNoteResponse,
    CreditNoteCreate,
    CreditNoteStatusUpdate,
    CreditNoteLinkCreate,
    CreditNoteLinkResponse,
)
from app.services.activity import log_invoice_activity

router = APIRouter(prefix="/credit-notes", tags=["Credit Notes"])

STORAGE_PATH = "storage/credit_notes"
os.makedirs(STORAGE_PATH, exist_ok=True)

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg"}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _parse_amount(val) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        cleaned = str(val).replace("£", "").replace(",", "").strip()
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_date(val) -> Optional[date]:
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


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[CreditNoteResponse])
def get_credit_notes(
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
    is_paid: Optional[bool] = None,
    is_approved_to_pay: Optional[bool] = None,
    supplier: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    query = db.query(CreditNote)

    if is_paid is not None:
        query = query.filter(CreditNote.is_paid == is_paid)
    if is_approved_to_pay is not None:
        query = query.filter(CreditNote.is_approved_to_pay == is_approved_to_pay)
    if supplier:
        query = query.filter(CreditNote.supplier_name_raw.ilike(f"%{supplier}%"))
    if review_status:
        query = query.filter(CreditNote.review_status == review_status)

    return (
        query.order_by(CreditNote.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{credit_note_id}", response_model=CreditNoteResponse)
def get_credit_note(
    credit_note_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    cn = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return cn


# ── File download ─────────────────────────────────────────────────────────────

@router.get("/{credit_note_id}/file")
def get_credit_note_file(
    credit_note_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    cn = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")
    if not cn.file_id:
        raise HTTPException(status_code=404, detail="No file attached to this credit note")

    invoice_file = db.query(InvoiceFile).filter(InvoiceFile.id == cn.file_id).first()
    if not invoice_file:
        raise HTTPException(status_code=404, detail="File record not found")
    if not os.path.exists(invoice_file.stored_path):
        raise HTTPException(status_code=404, detail="Stored file not found on disk")

    return FileResponse(
        path=invoice_file.stored_path,
        media_type=invoice_file.mime_type or "application/octet-stream",
        filename=invoice_file.original_filename,
        headers={"Content-Disposition": f'inline; filename="{invoice_file.original_filename}"'},
    )


# ── Upload PDF (skeleton, no OCR) ─────────────────────────────────────────────

@router.post("/upload", response_model=CreditNoteResponse)
def upload_credit_note(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    try:
        contents = file.file.read()

        if not contents:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum 20MB.")
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        original_name = os.path.basename(file.filename or "uploaded_file")
        extension = os.path.splitext(original_name)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file extension")

        file_hash = hashlib.sha256(contents).hexdigest()
        existing = db.query(InvoiceFile).filter(InvoiceFile.file_hash == file_hash).first()
        if existing:
            raise HTTPException(status_code=409, detail="Duplicate file")

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

        cn = CreditNote(
            file_id=invoice_file.id,
            ocr_status="pending",
            extraction_status="pending",
            review_status="pending",
        )
        db.add(cn)
        db.flush()

        log_invoice_activity(
            db=db,
            event_type="credit_note_uploaded",
            event_label="Credit note uploaded",
            invoice_id=None,
            changed_by=actor.id,
            new_values={"credit_note_id": cn.id, "original_filename": original_name, "file_id": invoice_file.id},
        )

        db.commit()
        db.refresh(cn)
        return cn

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Upload failed")


# ── Manual entry ──────────────────────────────────────────────────────────────

@router.post("/manual", response_model=CreditNoteResponse)
def create_manual_credit_note(
    data: CreditNoteCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    try:
        net_amount = data.net_amount
        if net_amount is None and data.vat_amount is not None:
            net_amount = data.gross_amount - data.vat_amount

        cn = CreditNote(
            file_id=None,
            supplier_name_raw=data.supplier_name_raw,
            paying_entity_raw=data.paying_entity_raw,
            paying_entity_id=data.paying_entity_id,
            project_id=data.project_id,
            credit_number=data.credit_number,
            credit_date=data.credit_date,
            gross_amount=data.gross_amount,
            vat_amount=data.vat_amount,
            net_amount=net_amount,
            currency=data.currency,
            ocr_status="manual",
            extraction_status="manual",
            review_status="auto_accepted",
            is_legacy=False,
        )
        db.add(cn)
        db.flush()

        log_invoice_activity(
            db=db,
            event_type="credit_note_created_manual",
            event_label="Credit note created manually",
            invoice_id=None,
            changed_by=actor.id,
            new_values={
                "credit_note_id": cn.id,
                "supplier_name_raw": data.supplier_name_raw,
                "credit_number": data.credit_number,
                "gross_amount": str(data.gross_amount),
                "credit_date": data.credit_date.isoformat(),
                "project_id": data.project_id,
                "currency": data.currency,
            },
        )

        db.commit()
        db.refresh(cn)
        return cn

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create credit note: {str(e)}")


# ── Edit fields ───────────────────────────────────────────────────────────────

@router.patch("/{credit_note_id}", response_model=CreditNoteResponse)
def update_credit_note(
    credit_note_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    cn = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")

    allowed_fields = {
        "credit_number", "supplier_name_raw", "paying_entity_raw",
        "paying_entity_id", "project_id", "credit_date",
        "gross_amount", "vat_amount", "net_amount",
        "review_status", "ocr_status", "extraction_status",
        "is_legacy", "currency",
    }
    amount_fields = {"gross_amount", "vat_amount", "net_amount"}
    date_fields = {"credit_date"}

    old_values = {f: str(getattr(cn, f)) if getattr(cn, f) is not None else None for f in allowed_fields}

    for key, value in data.items():
        if key not in allowed_fields:
            continue
        if key in amount_fields:
            setattr(cn, key, _parse_amount(value))
        elif key in date_fields:
            setattr(cn, key, _parse_date(value))
        else:
            setattr(cn, key, value)

    db.flush()
    new_values = {f: str(getattr(cn, f)) if getattr(cn, f) is not None else None for f in allowed_fields}

    log_invoice_activity(
        db=db,
        event_type="credit_note_updated",
        event_label="Credit note manually edited",
        invoice_id=None,
        changed_by=actor.id,
        old_values={**old_values, "credit_note_id": credit_note_id},
        new_values={**new_values, "credit_note_id": credit_note_id},
    )

    db.commit()
    db.refresh(cn)
    return cn


# ── Status toggles ────────────────────────────────────────────────────────────

@router.patch("/{credit_note_id}/status", response_model=CreditNoteResponse)
def update_credit_note_status(
    credit_note_id: int,
    status: CreditNoteStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    if status.is_paid is not None and not has_permission(actor, Permission.TOGGLE_PAID):
        raise HTTPException(403, "You don't have permission to mark credit notes as paid.")
    if status.is_approved_to_pay is not None and not has_permission(actor, Permission.APPROVE_TO_PAY):
        raise HTTPException(403, "Only partners or admins can approve credit notes to pay.")
    if status.is_legacy is not None and not has_permission(actor, Permission.EDIT_INVOICE):
        raise HTTPException(403, "You don't have permission to toggle legacy.")

    cn = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")

    old_values = {
        "is_paid": cn.is_paid,
        "is_approved_to_pay": cn.is_approved_to_pay,
        "is_legacy": cn.is_legacy,
    }

    if status.is_paid is not None:
        cn.is_paid = status.is_paid
    if status.is_approved_to_pay is not None:
        cn.is_approved_to_pay = status.is_approved_to_pay
    if status.is_legacy is not None:
        cn.is_legacy = status.is_legacy

    db.flush()
    db.refresh(cn)

    new_values = {
        "is_paid": cn.is_paid,
        "is_approved_to_pay": cn.is_approved_to_pay,
        "is_legacy": cn.is_legacy,
    }

    if old_values["is_approved_to_pay"] != new_values["is_approved_to_pay"] and new_values["is_approved_to_pay"]:
        log_invoice_activity(
            db=db,
            event_type="credit_note_approved",
            event_label="Credit note approved to pay",
            invoice_id=None,
            changed_by=actor.id,
            old_values={"is_approved_to_pay": old_values["is_approved_to_pay"], "credit_note_id": credit_note_id},
            new_values={"is_approved_to_pay": new_values["is_approved_to_pay"], "credit_note_id": credit_note_id},
        )

    if old_values["is_paid"] != new_values["is_paid"] and new_values["is_paid"]:
        log_invoice_activity(
            db=db,
            event_type="credit_note_paid",
            event_label="Credit note marked paid",
            invoice_id=None,
            changed_by=actor.id,
            old_values={"is_paid": old_values["is_paid"], "credit_note_id": credit_note_id},
            new_values={"is_paid": new_values["is_paid"], "credit_note_id": credit_note_id},
        )

    if old_values["is_legacy"] != new_values["is_legacy"]:
        log_invoice_activity(
            db=db,
            event_type="credit_note_legacy_toggled",
            event_label=f"Credit note legacy toggled: {new_values['is_legacy']}",
            invoice_id=None,
            changed_by=actor.id,
            old_values={"is_legacy": old_values["is_legacy"], "credit_note_id": credit_note_id},
            new_values={"is_legacy": new_values["is_legacy"], "credit_note_id": credit_note_id},
        )

    db.commit()
    db.refresh(cn)
    return cn


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{credit_note_id}")
def delete_credit_note(
    credit_note_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.DELETE_INVOICE)),
):
    cn = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")

    old_values = {
        "credit_note_id": cn.id,
        "credit_number": cn.credit_number,
        "supplier_name_raw": cn.supplier_name_raw,
        "gross_amount": str(cn.gross_amount) if cn.gross_amount is not None else None,
    }

    invoice_file = None
    if cn.file_id:
        invoice_file = db.query(InvoiceFile).filter(InvoiceFile.id == cn.file_id).first()
    stored_path = invoice_file.stored_path if invoice_file else None

    try:
        # Remove links before deleting the credit note
        db.query(CreditNoteLink).filter(
            CreditNoteLink.credit_note_id == cn.id
        ).delete(synchronize_session=False)

        log_invoice_activity(
            db=db,
            event_type="credit_note_deleted",
            event_label="Credit note deleted",
            invoice_id=None,
            changed_by=actor.id,
            old_values=old_values,
        )

        db.delete(cn)
        if invoice_file:
            db.delete(invoice_file)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete credit note: {str(e)}")

    if stored_path and os.path.exists(stored_path):
        try:
            os.remove(stored_path)
        except OSError:
            pass

    return {"message": "Credit note deleted successfully"}


# ── Links ─────────────────────────────────────────────────────────────────────

@router.get("/{credit_note_id}/links", response_model=List[CreditNoteLinkResponse])
def get_credit_note_links(
    credit_note_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    cn = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return db.query(CreditNoteLink).filter(CreditNoteLink.credit_note_id == credit_note_id).all()


@router.post("/{credit_note_id}/links", response_model=CreditNoteLinkResponse)
def create_credit_note_link(
    credit_note_id: int,
    link_data: CreditNoteLinkCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    cn = db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")

    # Verify invoice exists if provided
    if link_data.invoice_id is not None:
        from app.models.models import Invoice
        inv = db.query(Invoice).filter(Invoice.id == link_data.invoice_id).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")

    link = CreditNoteLink(
        credit_note_id=credit_note_id,
        invoice_id=link_data.invoice_id,
        allocated_amount=link_data.allocated_amount,
        created_by=actor.id,
    )
    db.add(link)
    db.flush()

    log_invoice_activity(
        db=db,
        event_type="credit_note_linked",
        event_label="Credit note linked to invoice",
        invoice_id=link_data.invoice_id,
        changed_by=actor.id,
        new_values={
            "credit_note_id": credit_note_id,
            "invoice_id": link_data.invoice_id,
            "allocated_amount": str(link_data.allocated_amount) if link_data.allocated_amount is not None else None,
            "link_id": link.id,
        },
    )

    db.commit()
    db.refresh(link)
    return link


@router.delete("/{credit_note_id}/links/{link_id}")
def delete_credit_note_link(
    credit_note_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.EDIT_INVOICE)),
):
    link = db.query(CreditNoteLink).filter(
        CreditNoteLink.id == link_id,
        CreditNoteLink.credit_note_id == credit_note_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    log_invoice_activity(
        db=db,
        event_type="credit_note_unlinked",
        event_label="Credit note unlinked from invoice",
        invoice_id=link.invoice_id,
        changed_by=actor.id,
        old_values={
            "credit_note_id": credit_note_id,
            "invoice_id": link.invoice_id,
            "link_id": link_id,
        },
    )

    db.delete(link)
    db.commit()
    return {"message": "Link removed successfully"}
