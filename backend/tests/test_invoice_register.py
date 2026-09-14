from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.invoices import create_manual_invoice, get_invoices, update_invoice
from app.api.recurring import update as update_recurring
from app.models.models import Invoice, Project
from app.schemas.invoice import ManualInvoiceCreate
from app.schemas.recurring_invoice import RecurringInvoiceCreate, RecurringInvoiceUpdate
from app.services.recurring_invoice_service import (
    _generate_one,
    create_recurring_invoice,
    process_due_recurring_invoices,
)

TODAY = date.today()


def make_invoice(db, **overrides):
    defaults = dict(
        supplier_name_raw="Acme Ltd",
        paying_entity_raw="Acme Entity",
        invoice_number="INV-1",
        invoice_date=TODAY,
        gross_amount=Decimal("100.00"),
        currency="GBP",
        ocr_status="manual",
        extraction_status="manual",
        review_status="auto_accepted",
        is_legacy=False,
        expense_nature="invoice",
    )
    defaults.update(overrides)
    invoice = Invoice(**defaults)
    db.add(invoice)
    db.flush()
    return invoice


# ── Expense nature ──────────────────────────────────────────────────────────

def test_expense_nature_defaults_to_invoice_when_unset(db_session):
    invoice = Invoice(
        supplier_name_raw="No Nature Ltd",
        invoice_number="INV-9",
        invoice_date=TODAY,
        gross_amount=Decimal("50.00"),
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    assert invoice.expense_nature == "invoice"


def test_manual_invoice_create_rejects_invalid_expense_nature():
    with pytest.raises(ValueError):
        ManualInvoiceCreate(
            supplier_name_raw="Acme",
            invoice_number="INV-1",
            gross_amount=Decimal("10"),
            invoice_date=TODAY,
            paying_entity_raw="Acme Entity",
            project_id=1,
            expense_nature="bogus",
        )


def test_create_manual_invoice_default_and_accrual(db_session, actor):
    default_data = ManualInvoiceCreate(
        supplier_name_raw="Acme",
        invoice_number="INV-D",
        gross_amount=Decimal("10"),
        invoice_date=TODAY,
        paying_entity_raw="Acme Entity",
        project_id=1,
    )
    default_invoice = create_manual_invoice(invoice_data=default_data, db=db_session, actor=actor)
    assert default_invoice.expense_nature == "invoice"

    accrual_data = ManualInvoiceCreate(
        supplier_name_raw="Acme",
        invoice_number="INV-A",
        gross_amount=Decimal("10"),
        invoice_date=TODAY,
        paying_entity_raw="Acme Entity",
        project_id=1,
        expense_nature="accrual",
    )
    accrual_invoice = create_manual_invoice(invoice_data=accrual_data, db=db_session, actor=actor)
    assert accrual_invoice.expense_nature == "accrual"
    assert accrual_invoice.aging_bucket == "1-30"


def test_update_invoice_can_switch_to_accrual(db_session, actor):
    invoice = make_invoice(db_session)
    db_session.commit()

    updated = update_invoice(invoice_id=invoice.id, data={"expense_nature": "accrual"}, db=db_session, actor=actor)
    assert updated.expense_nature == "accrual"


def test_update_invoice_rejects_invalid_expense_nature(db_session, actor):
    invoice = make_invoice(db_session)
    db_session.commit()

    with pytest.raises(HTTPException) as excinfo:
        update_invoice(invoice_id=invoice.id, data={"expense_nature": "bogus"}, db=db_session, actor=actor)
    assert excinfo.value.status_code == 400


# ── Recurring inheritance ────────────────────────────────────────────────────

def test_recurring_template_generates_invoice_with_same_nature(db_session, actor):
    body = RecurringInvoiceCreate(
        supplier_name_raw="Recurring Co",
        invoice_number_base="REC-1",
        gross_amount=Decimal("200"),
        paying_entity_raw="Recurring Entity",
        project_id=1,
        frequency="monthly",
        start_date=TODAY - timedelta(days=1),  # due in the past -> generates immediately
        expense_nature="accrual",
    )
    recurring = create_recurring_invoice(db_session, body, created_by=actor.id)
    assert recurring.expense_nature == "accrual"
    assert recurring.occurrence_count == 1

    generated = (
        db_session.query(Invoice)
        .filter(Invoice.invoice_number == "REC-1-1")
        .one()
    )
    assert generated.expense_nature == "accrual"

    # A later scheduled run must keep inheriting the template's nature, not
    # just the first, immediately-generated occurrence.
    second = _generate_one(db_session, recurring)
    db_session.commit()
    assert second.expense_nature == "accrual"


def test_recurring_update_changes_future_inherited_nature(db_session, actor):
    body = RecurringInvoiceCreate(
        supplier_name_raw="Recurring Co",
        invoice_number_base="REC-2",
        gross_amount=Decimal("200"),
        paying_entity_raw="Recurring Entity",
        project_id=1,
        frequency="monthly",
        start_date=TODAY + timedelta(days=30),  # not due yet -> no immediate generation
    )
    recurring = create_recurring_invoice(db_session, body, created_by=actor.id)
    assert recurring.expense_nature == "invoice"

    update_recurring(
        recurring_id=recurring.id,
        body=RecurringInvoiceUpdate(expense_nature="accrual"),
        db=db_session,
        _=actor,
    )
    db_session.refresh(recurring)
    assert recurring.expense_nature == "accrual"

    generated = _generate_one(db_session, recurring)
    db_session.commit()
    assert generated.expense_nature == "accrual"


# ── Filtering, sorting, pagination ──────────────────────────────────────────

def _seed_register(db_session):
    invoices = [
        make_invoice(db_session, invoice_number="A", supplier_name_raw="Alpha", gross_amount=Decimal("10"),
                     invoice_date=TODAY - timedelta(days=15), expense_nature="invoice", project_id=1),
        make_invoice(db_session, invoice_number="B", supplier_name_raw="Beta", gross_amount=Decimal("20"),
                     invoice_date=TODAY - timedelta(days=45), expense_nature="accrual", project_id=1),
        make_invoice(db_session, invoice_number="C", supplier_name_raw="Gamma", gross_amount=Decimal("30"),
                     invoice_date=TODAY - timedelta(days=75), expense_nature="invoice", project_id=2),
        make_invoice(db_session, invoice_number="D", supplier_name_raw="Delta", gross_amount=Decimal("40"),
                     invoice_date=TODAY - timedelta(days=120), expense_nature="accrual", project_id=2),
        make_invoice(db_session, invoice_number="E", supplier_name_raw="Epsilon", gross_amount=Decimal("50"),
                     invoice_date=None, expense_nature="invoice", project_id=None),
        make_invoice(db_session, invoice_number="F", supplier_name_raw="Zeta", gross_amount=Decimal("60"),
                     invoice_date=TODAY + timedelta(days=10), expense_nature="invoice", project_id=None),
    ]
    db_session.commit()
    return invoices


def test_aging_bucket_filter_matches_compute_aging(db_session, actor):
    _seed_register(db_session)

    cases = {
        "1-30": {"A"}, "31-60": {"B"}, "61-90": {"C"}, "90+": {"D"},
        "Not dated": {"E"}, "Future dated": {"F"},
    }
    for bucket, expected_numbers in cases.items():
        result = get_invoices(db=db_session, actor=actor, aging_bucket=bucket, limit=100, offset=0)
        assert {i.invoice_number for i in result.items} == expected_numbers, bucket
        for item in result.items:
            assert item.aging_bucket == bucket


def test_expense_nature_filter(db_session, actor):
    _seed_register(db_session)
    result = get_invoices(db=db_session, actor=actor, expense_nature="accrual", limit=100, offset=0)
    assert {i.invoice_number for i in result.items} == {"B", "D"}
    assert result.total == 2


def test_project_filter(db_session, actor):
    _seed_register(db_session)
    result = get_invoices(db=db_session, actor=actor, project_id=2, limit=100, offset=0)
    assert {i.invoice_number for i in result.items} == {"C", "D"}


def test_search_matches_supplier_and_invoice_number(db_session, actor):
    _seed_register(db_session)
    by_supplier = get_invoices(db=db_session, actor=actor, search="gamma", limit=100, offset=0)
    assert {i.invoice_number for i in by_supplier.items} == {"C"}

    by_number = get_invoices(db=db_session, actor=actor, search="D", limit=100, offset=0)
    assert {i.invoice_number for i in by_number.items} == {"D"}


def test_invalid_sort_by_rejected(db_session, actor):
    with pytest.raises(HTTPException) as excinfo:
        get_invoices(db=db_session, actor=actor, sort_by="not_a_field")
    assert excinfo.value.status_code == 400


def test_invalid_sort_dir_rejected(db_session, actor):
    with pytest.raises(HTTPException) as excinfo:
        get_invoices(db=db_session, actor=actor, sort_dir="sideways")
    assert excinfo.value.status_code == 400


def test_invalid_aging_bucket_rejected(db_session, actor):
    with pytest.raises(HTTPException) as excinfo:
        get_invoices(db=db_session, actor=actor, aging_bucket="ancient")
    assert excinfo.value.status_code == 400


def test_sort_by_aging_puts_undated_last_both_directions(db_session, actor):
    _seed_register(db_session)

    asc = get_invoices(db=db_session, actor=actor, sort_by="aging", sort_dir="asc", limit=100, offset=0)
    desc = get_invoices(db=db_session, actor=actor, sort_by="aging", sort_dir="desc", limit=100, offset=0)

    assert asc.items[-1].invoice_number == "E"  # Not dated
    assert desc.items[-1].invoice_number == "E"

    dated_asc = [i.aging_days for i in asc.items if i.aging_days is not None]
    assert dated_asc == sorted(dated_asc)

    dated_desc = [i.aging_days for i in desc.items if i.aging_days is not None]
    assert dated_desc == sorted(dated_desc, reverse=True)


def test_sort_by_project_name_via_join(db_session, actor):
    project_z = Project(id=1, name="Zulu Project")
    project_a = Project(id=2, name="Alpha Project")
    db_session.add_all([project_z, project_a])
    db_session.commit()

    _seed_register(db_session)  # project_id 1 -> Zulu, project_id 2 -> Alpha, None -> unmapped

    result = get_invoices(db=db_session, actor=actor, sort_by="project", sort_dir="asc", limit=100, offset=0)
    numbers_in_order = [i.invoice_number for i in result.items]
    # Alpha Project (C, D) sorts before Zulu Project (A, B); unmapped (E, F) last.
    assert numbers_in_order.index("C") < numbers_in_order.index("A")
    assert numbers_in_order.index("E") > numbers_in_order.index("A")
    assert numbers_in_order.index("E") > numbers_in_order.index("C")


def test_pagination_total_and_paging_covers_every_row(db_session, actor):
    _seed_register(db_session)

    page1 = get_invoices(db=db_session, actor=actor, sort_by="gross_amount", sort_dir="asc", limit=4, offset=0)
    page2 = get_invoices(db=db_session, actor=actor, sort_by="gross_amount", sort_dir="asc", limit=4, offset=4)

    assert page1.total == 6
    assert page2.total == 6
    assert len(page1.items) == 4
    assert len(page2.items) == 2

    all_numbers = [i.invoice_number for i in page1.items] + [i.invoice_number for i in page2.items]
    assert all_numbers == ["A", "B", "C", "D", "E", "F"]  # ascending gross_amount order
    assert len(set(all_numbers)) == 6  # no duplicate/skipped rows across pages


def test_stable_pagination_with_tied_sort_values(db_session, actor):
    # Every invoice ties on gross_amount, so only the id tiebreaker keeps
    # paging deterministic.
    for i in range(10):
        make_invoice(
            db_session,
            invoice_number=f"TIE-{i}",
            supplier_name_raw="Tied Supplier",
            gross_amount=Decimal("99.99"),
            invoice_date=TODAY,
        )
    db_session.commit()

    seen = []
    for offset in (0, 3, 6, 9):
        page = get_invoices(
            db=db_session, actor=actor, search="Tied", sort_by="gross_amount", sort_dir="asc",
            limit=3, offset=offset,
        )
        seen.extend(i.invoice_number for i in page.items)

    assert len(seen) == len(set(seen)) == 10


def test_filtering_and_attachments_are_independent(db_session, actor):
    """New filters/aging must not touch file_id or any attachment fields."""
    with_file = make_invoice(db_session, invoice_number="HAS-FILE", file_id=None, invoice_date=TODAY)
    # Simulate an invoice that has a stored file by setting file_id directly;
    # we only assert it round-trips untouched, not exercise file storage.
    with_file.file_id = 12345
    db_session.commit()

    result = get_invoices(db=db_session, actor=actor, search="HAS-FILE", limit=10, offset=0)
    assert len(result.items) == 1
    assert result.items[0].file_id == 12345
