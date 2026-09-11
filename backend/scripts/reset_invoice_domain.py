"""Guarded one-time reset for invoice-domain data only.

Default behaviour is a read-only dry run.  Database and attachment deletion are
possible only with all explicit command-line safety flags.  This script never
touches users, entities, projects, suppliers, mapping rules, sessions, tokens,
or entity-bank balances.
"""

from __future__ import annotations

import argparse
import shutil
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
    ExtractionResult,
    Invoice,
    InvoiceActivityLog,
    InvoiceAuditLog,
    InvoiceFile,
    InvoiceFlag,
    Override,
    RecurringInvoice,
)


CONFIRMATION = "RESET-INVOICE-DOMAIN"


def count_files(folder: str) -> int:
    directory = storage_root() / folder
    return sum(1 for path in directory.rglob("*") if path.is_file()) if directory.is_dir() else 0


def scope(db) -> dict[str, int]:
    return {
        "credit_note_links": db.query(CreditNoteLink).count(),
        "approval_requests": db.query(ApprovalRequest).count(),
        "invoice_flags": db.query(InvoiceFlag).count(),
        "invoice_activity_logs": db.query(InvoiceActivityLog).count(),
        "invoice_audit_log": db.query(InvoiceAuditLog).count(),
        "overrides": db.query(Override).count(),
        "extraction_results": db.query(ExtractionResult).count(),
        "generic_invoice_audit_rows": db.query(AuditLog).filter(
            AuditLog.target_type.in_(("invoice", "invoices", "credit_note", "credit_notes", "invoice_file"))
        ).count(),
        "credit_notes": db.query(CreditNote).count(),
        "recurring_invoices": db.query(RecurringInvoice).count(),
        "invoices": db.query(Invoice).count(),
        "invoice_files": db.query(InvoiceFile).count(),
        "physical_invoice_pdfs": count_files("invoices"),
        "physical_credit_note_pdfs": count_files("credit_notes"),
    }


def clear_attachment_folder(folder: str) -> None:
    root = storage_root().resolve()
    directory = (root / folder).resolve()
    if not directory.is_relative_to(root):
        raise RuntimeError(f"Refusing to clear path outside storage root: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoice-domain reset; dry run by default.")
    parser.add_argument("--execute", action="store_true", help="Perform the irreversible reset.")
    parser.add_argument("--include-recurring", action="store_true", help="Also clear recurring templates.")
    parser.add_argument("--local-pdf-archive-verified", action="store_true", help="Confirm the verified local PDF archive exists.")
    parser.add_argument("--confirmation", help=f"Must equal {CONFIRMATION!r} to execute.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        current_scope = scope(db)
        print("=== INVOICE-DOMAIN RESET PREVIEW ===")
        for name, count in current_scope.items():
            print(f"{name}: {count}")
        print("\nUntouched: users, entities, projects, suppliers, mapping_rules, sessions, user_tokens, entity_bank_balances.")

        if not args.execute:
            print("\nDRY RUN ONLY — no database rows or files were changed.")
            return 0

        if not args.include_recurring:
            parser.error("--include-recurring is required for the approved invoice-domain reset.")
        if not args.local_pdf_archive_verified:
            parser.error("--local-pdf-archive-verified is required before deletion.")
        if args.confirmation != CONFIRMATION:
            parser.error(f"--confirmation {CONFIRMATION!r} is required before deletion.")

        with db.begin():
            db.query(CreditNoteLink).delete(synchronize_session=False)
            db.query(ApprovalRequest).delete(synchronize_session=False)
            db.query(InvoiceFlag).delete(synchronize_session=False)
            db.query(InvoiceActivityLog).delete(synchronize_session=False)
            db.query(InvoiceAuditLog).delete(synchronize_session=False)
            db.query(Override).delete(synchronize_session=False)
            db.query(ExtractionResult).delete(synchronize_session=False)
            db.query(AuditLog).filter(
                AuditLog.target_type.in_(("invoice", "invoices", "credit_note", "credit_notes", "invoice_file"))
            ).delete(synchronize_session=False)
            db.query(CreditNote).delete(synchronize_session=False)
            db.query(RecurringInvoice).delete(synchronize_session=False)
            db.query(Invoice).delete(synchronize_session=False)
            db.query(InvoiceFile).delete(synchronize_session=False)

        clear_attachment_folder("invoices")
        clear_attachment_folder("credit_notes")
        print("\nRESET COMPLETE — invoice-domain database rows and persistent attachment folders were cleared.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
