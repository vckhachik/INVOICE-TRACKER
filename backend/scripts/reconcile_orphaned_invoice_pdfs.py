"""Read-only evidence matcher for orphaned invoice PDFs.

This script never writes files, updates database rows, calls Azure, or calls an
LLM.  It compares the readable text of PDFs in the configured invoice-storage
folder with invoice metadata already in Postgres.  It prints only conservative
candidate matches and the evidence supporting each candidate.

Run from the backend directory in an environment that contains both ``app`` and
``scripts`` (for example, a container image that copies the scripts folder):

    python scripts/reconcile_orphaned_invoice_pdfs.py

The production image must be verified to include the script before running it.
A deployment never runs this script automatically.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.storage import resolve_stored_path, storage_root
from app.db.database import SessionLocal
from app.models.models import Invoice, InvoiceFile


GENERIC_WORDS = {
    "LIMITED", "LTD", "LLP", "PLC", "COMPANY", "CO", "THE", "AND",
    "INVOICE", "TAX", "VAT", "UK", "GB", "LONDON", "FROM", "FOR",
}


@dataclass(frozen=True)
class InvoiceEvidence:
    invoice_id: int
    invoice_number: str | None
    supplier: str | None
    invoice_date: date | None
    gross_amount: Decimal | None
    net_amount: Decimal | None
    vat_amount: Decimal | None
    original_filename: str | None
    stored_path: str


@dataclass(frozen=True)
class PdfEvidence:
    path: Path
    text: str


@dataclass(frozen=True)
class Candidate:
    invoice_id: int
    pdf_name: str
    score: int
    evidence: tuple[str, ...]


def compact(value: object | None) -> str:
    """Upper-case text without punctuation, for stable invoice-number checks."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def words(value: object | None) -> set[str]:
    return {
        token for token in re.findall(r"[A-Z0-9]{3,}", str(value or "").upper())
        if token not in GENERIC_WORDS and not token.isdigit()
    }


def text_contains_compact(text: str, value: object | None) -> bool:
    needle = compact(value)
    return len(needle) >= 4 and needle in compact(text)


def amount_variants(value: Decimal | None) -> set[str]:
    if value is None:
        return set()
    amount = Decimal(value).quantize(Decimal("0.01"))
    return {
        f"{amount:.2f}",
        f"{amount:,.2f}",
        str(amount.normalize()),
    }


def text_has_amount(text: str, value: Decimal | None) -> bool:
    return any(re.search(rf"(?<![0-9]){re.escape(variant)}(?![0-9])", text) for variant in amount_variants(value))


def supplier_overlap(supplier: str | None, text: str) -> tuple[int, int]:
    supplier_words = words(supplier)
    if not supplier_words:
        return 0, 0
    matched = supplier_words & words(text)
    return len(matched), len(supplier_words)


def score_candidate(invoice: InvoiceEvidence, pdf: PdfEvidence) -> Candidate | None:
    """Score only evidence that can be shown to a reviewer.

    A candidate must have an exact invoice-number anchor, or both a meaningful
    supplier match and an amount/date anchor.  This prevents broad fuzzy matches.
    """
    searchable = f"{pdf.path.name}\n{pdf.text}"
    score = 0
    evidence: list[str] = []
    anchors = 0

    if text_contains_compact(searchable, invoice.invoice_number):
        score += 65
        anchors += 1
        evidence.append("exact invoice number")

    matched_supplier_words, supplier_word_count = supplier_overlap(invoice.supplier, searchable)
    if supplier_word_count and matched_supplier_words:
        ratio = matched_supplier_words / supplier_word_count
        if ratio >= 0.75 or (supplier_word_count >= 2 and matched_supplier_words >= 2):
            score += 20
            anchors += 1
            evidence.append(f"supplier words {matched_supplier_words}/{supplier_word_count}")
        elif ratio >= 0.5:
            score += 10
            evidence.append(f"supplier words {matched_supplier_words}/{supplier_word_count}")

    gross_matches = text_has_amount(searchable, invoice.gross_amount)
    if gross_matches:
        score += 25
        anchors += 1
        evidence.append("exact gross amount")

    if text_has_amount(searchable, invoice.net_amount):
        score += 8
        evidence.append("exact net amount")

    if text_has_amount(searchable, invoice.vat_amount):
        score += 7
        evidence.append("exact VAT amount")

    if invoice.invoice_date and invoice.invoice_date.isoformat() in searchable:
        score += 10
        anchors += 1
        evidence.append("ISO invoice date")

    filename_words = words(invoice.original_filename)
    name_matches = filename_words & words(pdf.path.name)
    if len(name_matches) >= 2:
        score += 10
        evidence.append(f"filename words: {', '.join(sorted(name_matches))}")

    # Reject a candidate unless it is tied by a strong invoice-number signal or
    # corroborated by two independent business facts.
    has_invoice_number = "exact invoice number" in evidence
    if not has_invoice_number and anchors < 2:
        return None
    if score < 45:
        return None

    return Candidate(invoice.invoice_id, pdf.path.name, score, tuple(evidence))


def extract_pdf_text(path: Path) -> str:
    """Extract text locally; no document leaves Railway."""
    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if text:
            return text[:200_000]
    except Exception:
        # Some malformed PDFs are still readable by Poppler, if it is installed.
        pass

    executable = shutil.which("pdftotext")
    if not executable:
        return ""
    completed = subprocess.run(
        [executable, "-layout", str(path), "-"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=30,
    )
    return completed.stdout[:200_000] if completed.returncode == 0 else ""


def missing_invoice_evidence(db) -> list[InvoiceEvidence]:
    rows = (
        db.query(Invoice, InvoiceFile)
        .join(InvoiceFile, Invoice.file_id == InvoiceFile.id)
        .order_by(Invoice.id)
        .all()
    )
    missing: list[InvoiceEvidence] = []
    for invoice, file in rows:
        try:
            exists = resolve_stored_path(file.stored_path).is_file()
        except ValueError:
            exists = False
        if not exists:
            missing.append(
                InvoiceEvidence(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    supplier=invoice.supplier_name_raw,
                    invoice_date=invoice.invoice_date,
                    gross_amount=invoice.gross_amount,
                    net_amount=invoice.net_amount,
                    vat_amount=invoice.vat_amount,
                    original_filename=file.original_filename,
                    stored_path=file.stored_path,
                )
            )
    return missing


def orphan_pdfs(db) -> list[PdfEvidence]:
    expected_paths = set()
    for file in db.query(InvoiceFile).all():
        try:
            expected_paths.add(resolve_stored_path(file.stored_path).resolve())
        except ValueError:
            continue
    folder = storage_root() / "invoices"
    return [
        PdfEvidence(path=path, text=extract_pdf_text(path))
        for path in sorted(folder.glob("*"))
        if path.is_file() and path.resolve() not in expected_paths
    ]


def high_confidence_one_to_one(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Keep only unique, clearly-ahead candidates; never auto-accept a tie."""
    by_invoice: dict[int, list[Candidate]] = {}
    by_pdf: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_invoice.setdefault(candidate.invoice_id, []).append(candidate)
        by_pdf.setdefault(candidate.pdf_name, []).append(candidate)

    accepted: list[Candidate] = []
    for invoice_candidates in by_invoice.values():
        ranked = sorted(invoice_candidates, key=lambda item: item.score, reverse=True)
        best = ranked[0]
        runner_up = ranked[1].score if len(ranked) > 1 else 0
        pdf_ranked = sorted(by_pdf[best.pdf_name], key=lambda item: item.score, reverse=True)
        pdf_runner_up = pdf_ranked[1].score if len(pdf_ranked) > 1 else 0
        if best.score >= 85 and best.score - runner_up >= 15 and best.score - pdf_runner_up >= 15:
            accepted.append(best)
    return sorted(accepted, key=lambda item: (item.invoice_id, item.pdf_name))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-review",
        action="store_true",
        help="also print medium-confidence candidates (65+), for manual review",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        invoices = missing_invoice_evidence(db)
        pdfs = orphan_pdfs(db)
        candidates = [
            candidate
            for invoice in invoices
            for pdf in pdfs
            if (candidate := score_candidate(invoice, pdf)) is not None
        ]
        accepted = high_confidence_one_to_one(candidates)
        accepted_keys = {(item.invoice_id, item.pdf_name) for item in accepted}

        no_text = sum(1 for pdf in pdfs if not pdf.text.strip())
        print("=== READ-ONLY PDF EVIDENCE MATCHER ===")
        print(f"Missing invoice records considered: {len(invoices)}")
        print(f"Orphan PDFs considered: {len(pdfs)}")
        print(f"PDFs with no locally extractable text: {no_text}")
        print(f"High-confidence one-to-one candidates: {len(accepted)}")
        print()

        print("=== HIGH-CONFIDENCE CANDIDATES — REVIEW BEFORE ANY RECOVERY ===")
        for item in accepted:
            print(f"invoice_id={item.invoice_id} pdf={item.pdf_name} score={item.score} evidence={'; '.join(item.evidence)}")

        if args.show_review:
            print("\n=== MEDIUM-CONFIDENCE CANDIDATES — NOT SAFE TO APPLY ===")
            for item in sorted(candidates, key=lambda value: (-value.score, value.invoice_id, value.pdf_name)):
                if item.score >= 65 and (item.invoice_id, item.pdf_name) not in accepted_keys:
                    print(f"invoice_id={item.invoice_id} pdf={item.pdf_name} score={item.score} evidence={'; '.join(item.evidence)}")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
