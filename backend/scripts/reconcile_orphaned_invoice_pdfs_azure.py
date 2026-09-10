"""Analysis-only Azure OCR reconciliation for orphaned invoice PDFs.

With ``--execute`` this sends only orphaned PDFs to Azure Document Intelligence,
then compares returned business fields to invoice metadata already in Postgres.
It never writes files or changes database rows, and never calls an LLM.

Run inside the deployed backend container:
    python /app/scripts/reconcile_orphaned_invoice_pdfs_azure.py --execute
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

try:  # Supports both ``python scripts/...`` and package-based tests.
    from scripts.reconcile_orphaned_invoice_pdfs import (
        InvoiceEvidence,
        compact,
        missing_invoice_evidence,
        orphan_pdfs,
        supplier_overlap,
    )
except ModuleNotFoundError:
    from reconcile_orphaned_invoice_pdfs import (
        InvoiceEvidence,
        compact,
        missing_invoice_evidence,
        orphan_pdfs,
        supplier_overlap,
    )

from app.db.database import SessionLocal
from app.services.extraction import extract_invoice


def as_decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("amount") or value.get("value")
    elif hasattr(value, "amount"):
        value = value.amount
    try:
        return Decimal(str(value).replace(",", "").replace("£", "").replace("$", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def as_date(value: object | None) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def same_amount(left: Decimal | None, right: Decimal | None) -> bool:
    return left is not None and right is not None and abs(left - right) <= Decimal("0.01")


def score(invoice: InvoiceEvidence, fields: dict) -> tuple[int, tuple[str, ...]]:
    points, anchors, evidence = 0, 0, []
    if compact(fields.get("invoice_number")) and compact(fields.get("invoice_number")) == compact(invoice.invoice_number):
        points += 70
        anchors += 1
        evidence.append("Azure invoice number exact")

    matched, total = supplier_overlap(invoice.supplier, str(fields.get("supplier_name_raw") or ""))
    if total and (matched / total >= 0.75 or (total >= 2 and matched >= 2)):
        points += 20
        anchors += 1
        evidence.append(f"Azure supplier words {matched}/{total}")

    if same_amount(invoice.gross_amount, as_decimal(fields.get("gross_amount"))):
        points += 25
        anchors += 1
        evidence.append("Azure gross amount exact")
    if same_amount(invoice.net_amount, as_decimal(fields.get("net_amount"))):
        points += 8
        evidence.append("Azure net amount exact")
    if same_amount(invoice.vat_amount, as_decimal(fields.get("vat_amount"))):
        points += 7
        evidence.append("Azure VAT amount exact")
    if invoice.invoice_date and as_date(fields.get("invoice_date")) == invoice.invoice_date:
        points += 12
        anchors += 1
        evidence.append("Azure invoice date exact")

    # Exact invoice number still needs corroboration; supplier/amount alone is
    # never enough. This is intentionally stricter than fuzzy matching.
    if anchors < 2:
        return 0, ()
    return points, tuple(evidence)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="required before any Azure calls are made")
    parser.add_argument("--limit", type=int, default=None, help="analyse only the first N PDFs")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Refusing to call Azure without --execute")

    db = SessionLocal()
    try:
        invoices = missing_invoice_evidence(db)
        pdfs = orphan_pdfs(db)
        if args.limit is not None:
            pdfs = pdfs[:args.limit]
        print("=== AZURE ANALYSIS-ONLY RECONCILIATION ===")
        print(f"Missing invoice records: {len(invoices)}")
        print(f"Orphan PDFs to send to Azure: {len(pdfs)}")
        print("No database or file changes will be made.\n")

        candidates, failures = [], []
        for index, pdf in enumerate(pdfs, start=1):
            print(f"Analysing {index}/{len(pdfs)}: {pdf.path.name}")
            try:
                fields = extract_invoice(str(pdf.path)).get("extracted_fields", {}) or {}
            except Exception as exc:
                failures.append((pdf.path.name, str(exc)))
                continue
            for invoice in invoices:
                points, evidence = score(invoice, fields)
                if points:
                    candidates.append((invoice.invoice_id, pdf.path.name, points, evidence))

        by_invoice, by_pdf = defaultdict(list), defaultdict(list)
        for candidate in candidates:
            by_invoice[candidate[0]].append(candidate)
            by_pdf[candidate[1]].append(candidate)
        accepted = []
        for options in by_invoice.values():
            ranked = sorted(options, key=lambda item: item[2], reverse=True)
            best = ranked[0]
            invoice_runner_up = ranked[1][2] if len(ranked) > 1 else 0
            pdf_ranked = sorted(by_pdf[best[1]], key=lambda item: item[2], reverse=True)
            pdf_runner_up = pdf_ranked[1][2] if len(pdf_ranked) > 1 else 0
            if best[2] >= 90 and best[2] - invoice_runner_up >= 15 and best[2] - pdf_runner_up >= 15:
                accepted.append(best)
        accepted_keys = {(item[0], item[1]) for item in accepted}

        print("\n=== SUMMARY ===")
        print(f"Azure analysis failures: {len(failures)}")
        print(f"High-confidence one-to-one candidates: {len(accepted)}")
        print(f"Other evidence candidates: {len(candidates) - len(accepted)}")
        print("\n=== HIGH-CONFIDENCE — REVIEW BEFORE RECOVERY ===")
        for invoice_id, pdf_name, points, evidence in sorted(accepted):
            print(f"invoice_id={invoice_id} pdf={pdf_name} score={points} evidence={'; '.join(evidence)}")
        print("\n=== REVIEW CANDIDATES — NOT SAFE TO APPLY ===")
        for invoice_id, pdf_name, points, evidence in sorted(candidates, key=lambda item: (-item[2], item[0], item[1])):
            if (invoice_id, pdf_name) not in accepted_keys:
                print(f"invoice_id={invoice_id} pdf={pdf_name} score={points} evidence={'; '.join(evidence)}")
        if failures:
            print("\n=== AZURE FAILURES ===")
            for filename, error in failures:
                print(f"pdf={filename} error={error}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
