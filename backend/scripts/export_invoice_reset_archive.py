"""Print a complete, read-only invoice-domain archive as JSON.

This script is deliberately separate from any reset tooling.  It only reads
Postgres and inspects attachment paths; it never writes database rows, PDF
files, or storage directories.  Redirect its standard output to a local file
when running it through Railway SSH.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.storage import resolve_stored_path, storage_root
from app.db.database import SessionLocal
from app.models.models import (
    ApprovalRequest,
    CreditNote,
    CreditNoteLink,
    Entity,
    ExtractionResult,
    Invoice,
    InvoiceActivityLog,
    InvoiceAuditLog,
    InvoiceFile,
    InvoiceFlag,
    MappingRule,
    Override,
    Project,
    RecurringInvoice,
    Supplier,
    User,
)


def json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def row(model: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    values = {
        column.name: json_value(getattr(model, column.name))
        for column in model.__table__.columns
    }
    if extra:
        values.update({key: json_value(value) for key, value in extra.items()})
    return values


def attachment_state(stored_path: str | None) -> str:
    if not stored_path:
        return "no stored path"
    try:
        return "present" if resolve_stored_path(stored_path).is_file() else "missing"
    except (OSError, ValueError):
        return "invalid path"


def physical_pdf_count(folder: str) -> int:
    directory = storage_root() / folder
    return sum(1 for path in directory.rglob("*") if path.is_file()) if directory.is_dir() else 0


def archive() -> dict[str, Any]:
    db = SessionLocal()
    try:
        entities = {item.id: item.name for item in db.query(Entity).all()}
        projects = {item.id: item.name for item in db.query(Project).all()}
        users = {item.id: item.full_name for item in db.query(User).all()}
        files = {item.id: item for item in db.query(InvoiceFile).all()}
        invoice_file_ids = Counter(item.file_id for item in db.query(Invoice).all() if item.file_id)
        credit_file_ids = Counter(item.file_id for item in db.query(CreditNote).all() if item.file_id)

        invoices = []
        for item in db.query(Invoice).order_by(Invoice.id).all():
            file = files.get(item.file_id)
            invoices.append(row(item, {
                "entity_name": entities.get(item.paying_entity_id),
                "project_name": projects.get(item.project_id),
                "original_filename": file.original_filename if file else None,
                "stored_path": file.stored_path if file else None,
                "file_hash": file.file_hash if file else None,
                "attachment_state": attachment_state(file.stored_path) if file else "no file record",
            }))

        credit_notes = []
        for item in db.query(CreditNote).order_by(CreditNote.id).all():
            file = files.get(item.file_id)
            credit_notes.append(row(item, {
                "entity_name": entities.get(item.paying_entity_id),
                "project_name": projects.get(item.project_id),
                "original_filename": file.original_filename if file else None,
                "stored_path": file.stored_path if file else None,
                "file_hash": file.file_hash if file else None,
                "attachment_state": attachment_state(file.stored_path) if file else "no file record",
            }))

        file_rows = [row(item, {
            "attachment_state": attachment_state(item.stored_path),
            "invoice_reference_count": invoice_file_ids.get(item.id, 0),
            "credit_note_reference_count": credit_file_ids.get(item.id, 0),
        }) for item in files.values()]

        result = {
            "archive_format": "invoice-reset-archive/v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "summary": [{
                "invoice_count": len(invoices),
                "credit_note_count": len(credit_notes),
                "recurring_invoice_count": db.query(RecurringInvoice).count(),
                "invoice_file_count": len(file_rows),
                "physical_invoice_pdf_count": physical_pdf_count("invoices"),
                "physical_credit_note_pdf_count": physical_pdf_count("credit_notes"),
                "present_invoice_attachments": sum(item["attachment_state"] == "present" for item in invoices),
                "missing_invoice_attachments": sum(item["attachment_state"] == "missing" for item in invoices),
                "invoice_without_file_record": sum(item["attachment_state"] == "no file record" for item in invoices),
                "entity_count_preserved": len(entities),
                "project_count_preserved": len(projects),
                "supplier_count_preserved": db.query(Supplier).count(),
                "user_count_preserved": len(users),
            }],
            "invoices": invoices,
            "invoice_files": sorted(file_rows, key=lambda item: item["id"]),
            "credit_notes": credit_notes,
            "credit_note_links": [row(item, {"created_by_name": users.get(item.created_by)}) for item in db.query(CreditNoteLink).order_by(CreditNoteLink.id)],
            "recurring_invoices": [row(item, {
                "entity_name": entities.get(item.paying_entity_id),
                "project_name": projects.get(item.project_id),
                "created_by_name": users.get(item.created_by),
            }) for item in db.query(RecurringInvoice).order_by(RecurringInvoice.id)],
            "approval_requests": [row(item, {
                "requested_by_name": users.get(item.requested_by),
                "resolved_by_name": users.get(item.resolved_by),
            }) for item in db.query(ApprovalRequest).order_by(ApprovalRequest.id)],
            "invoice_flags": [row(item) for item in db.query(InvoiceFlag).order_by(InvoiceFlag.id)],
            "invoice_overrides": [row(item, {"changed_by_name": users.get(item.changed_by)}) for item in db.query(Override).order_by(Override.id)],
            "invoice_audit_log": [row(item, {"changed_by_name": users.get(item.changed_by)}) for item in db.query(InvoiceAuditLog).order_by(InvoiceAuditLog.id)],
            "invoice_activity_log": [row(item, {"changed_by_name": users.get(item.changed_by)}) for item in db.query(InvoiceActivityLog).order_by(InvoiceActivityLog.id)],
            "extraction_results": [row(item) for item in db.query(ExtractionResult).order_by(ExtractionResult.id)],
            "mapping_rules_preserved": [row(item, {
                "entity_name": entities.get(item.mapped_entity_id),
                "project_name": projects.get(item.mapped_project_id),
            }) for item in db.query(MappingRule).order_by(MappingRule.id)],
        }
        return result
    finally:
        db.close()


if __name__ == "__main__":
    print(json.dumps(archive(), ensure_ascii=False, indent=2, default=json_value))
