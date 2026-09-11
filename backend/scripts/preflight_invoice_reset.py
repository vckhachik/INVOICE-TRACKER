"""Print the exact scope of a proposed invoice-only reset.

This is a read-only preflight report.  It does not delete database rows, alter
PDFs, or create files.  Its purpose is to make the eventual reset scope
explicit and reviewable before a separate destructive script is ever written.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.storage import storage_root
from app.db.database import SessionLocal
from app.models.models import (
    ApprovalRequest,
    AuditLog,
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


def count_files(folder: str) -> int:
    directory = storage_root() / folder
    return sum(1 for path in directory.rglob("*") if path.is_file()) if directory.is_dir() else 0


def main() -> int:
    db = SessionLocal()
    try:
        invoice_audit_events = db.query(AuditLog).filter(
            AuditLog.target_type.in_(("invoice", "invoices", "credit_note", "credit_notes", "invoice_file"))
        ).count()
        report = {
            "mode": "READ-ONLY PRE-FLIGHT — NO RESET EXECUTED",
            "proposed_invoice_domain_tables": {
                "credit_note_links": db.query(CreditNoteLink).count(),
                "approval_requests": db.query(ApprovalRequest).count(),
                "invoice_flags": db.query(InvoiceFlag).count(),
                "invoice_activity_logs": db.query(InvoiceActivityLog).count(),
                "invoice_audit_log": db.query(InvoiceAuditLog).count(),
                "overrides": db.query(Override).count(),
                "extraction_results": db.query(ExtractionResult).count(),
                "credit_notes": db.query(CreditNote).count(),
                "recurring_invoices": db.query(RecurringInvoice).count(),
                "invoices": db.query(Invoice).count(),
                "invoice_files": db.query(InvoiceFile).count(),
            },
            "proposed_attachment_folders": {
                "persistent_root": str(storage_root()),
                "invoices": count_files("invoices"),
                "credit_notes": count_files("credit_notes"),
            },
            "requires_explicit_scope_decision": {
                "generic_audit_log_invoice_related_rows": invoice_audit_events,
                "recurring_invoices": "Include only if recurring templates should also start at zero.",
                "mapping_rules": "Preserve: they map suppliers/entities/projects and are not invoice records.",
            },
            "must_remain_untouched": {
                "users": db.query(User).count(),
                "entities": db.query(Entity).count(),
                "projects": db.query(Project).count(),
                "suppliers": db.query(Supplier).count(),
                "mapping_rules": db.query(MappingRule).count(),
            },
            "safety_gates": [
                "Current Postgres backup exists.",
                "Current backend-volume backup exists.",
                "A downloadable local copy of physical PDFs exists.",
                "The reset scope has been approved from this exact report.",
                "A five-PDF post-reset upload/retrieval test is planned.",
            ],
        }
        print(json.dumps(report, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
