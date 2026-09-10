from datetime import date
from decimal import Decimal

from scripts.reconcile_orphaned_invoice_pdfs import InvoiceEvidence
from scripts.reconcile_orphaned_invoice_pdfs_azure import score


def invoice() -> InvoiceEvidence:
    return InvoiceEvidence(
        invoice_id=1, invoice_number="INV-2026-001", supplier="Example Supplier Limited",
        invoice_date=date(2026, 8, 1), gross_amount=Decimal("120.00"),
        net_amount=Decimal("100.00"), vat_amount=Decimal("20.00"),
        original_filename="example.pdf", stored_path="storage/invoices/a.pdf",
    )


def test_exact_number_needs_corroboration():
    assert score(invoice(), {"invoice_number": "INV-2026-001"}) == (0, ())


def test_exact_number_supplier_and_amount_is_high_confidence():
    points, evidence = score(invoice(), {
        "invoice_number": "INV-2026-001",
        "supplier_name_raw": "Example Supplier Limited",
        "gross_amount": "120.00",
    })
    assert points >= 90
    assert "Azure invoice number exact" in evidence
