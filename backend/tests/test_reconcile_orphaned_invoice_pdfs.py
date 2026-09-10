from datetime import date
from decimal import Decimal
from pathlib import Path

from scripts.reconcile_orphaned_invoice_pdfs import (
    InvoiceEvidence,
    PdfEvidence,
    high_confidence_one_to_one,
    score_candidate,
)


def invoice() -> InvoiceEvidence:
    return InvoiceEvidence(
        invoice_id=1,
        invoice_number="INV-2026-001",
        supplier="Example Supplier Limited",
        invoice_date=date(2026, 8, 1),
        gross_amount=Decimal("120.00"),
        net_amount=Decimal("100.00"),
        vat_amount=Decimal("20.00"),
        original_filename="Example Supplier INV-2026-001.pdf",
        stored_path="storage/invoices/a.pdf",
    )


def test_invoice_number_and_amount_is_high_confidence():
    candidate = score_candidate(
        invoice(),
        PdfEvidence(Path("orphan.pdf"), "Invoice INV-2026-001\nTotal 120.00\nExample Supplier"),
    )

    assert candidate is not None
    assert candidate.score >= 85
    assert "exact invoice number" in candidate.evidence


def test_supplier_only_is_rejected():
    candidate = score_candidate(
        invoice(),
        PdfEvidence(Path("orphan.pdf"), "Example Supplier Limited"),
    )

    assert candidate is None


def test_tied_candidates_are_not_accepted():
    first = score_candidate(
        invoice(),
        PdfEvidence(Path("first.pdf"), "Invoice INV-2026-001\nTotal 120.00\nExample Supplier"),
    )
    second = score_candidate(
        invoice(),
        PdfEvidence(Path("second.pdf"), "Invoice INV-2026-001\nTotal 120.00\nExample Supplier"),
    )

    assert first is not None and second is not None
    assert high_confidence_one_to_one([first, second]) == []
