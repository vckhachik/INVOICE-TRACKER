from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import sessionmaker

from app.models.models import Entity, Invoice, Project, RecurringInvoice, User
from scripts.restore_recurring_templates import (
    RESTORED_EXPENSE_NATURE,
    apply_ready_records,
    evaluate_record,
    load_target_state,
    print_preview,
    run_preview,
)


def make_archive_record(**overrides):
    record = {
        "id": 7,
        "supplier_name_raw": "Social Security",
        "paying_entity_raw": None,
        "paying_entity_id": 38,
        "entity_name": "Valpre Capital Investments SARL",
        "project_id": 9,
        "project_name": "OTHER",
        "invoice_number_base": "Social Security",
        "gross_amount": "5290.45",
        "vat_amount": None,
        "net_amount": "5290.45",
        "currency": "GBP",
        "description": None,
        "frequency": "monthly",
        "frequency_interval": 1,
        "day_of_month": 1,
        "start_date": "2026-08-01",
        "end_date": None,
        "max_occurrences": None,
        "occurrence_count": 3,
        "next_due_date": "2026-01-01",  # in the past relative to any test "today"
        "last_generated_at": "2026-09-01T06:00:00.183374",
        "is_active": True,
        "created_by": 3,
        "created_by_name": "Salam Nassar",
        "created_at": "2026-08-24T13:42:29.703924",
        "updated_at": "2026-09-01T00:00:00.002630",
    }
    record.update(overrides)
    return record


@pytest.fixture()
def target_db(db_session):
    """Seed entities/projects/users that a well-formed archive record
    resolves against, mirroring the real archive's references."""
    entity = Entity(id=38, name="Valpre Capital Investments SARL")
    project = Project(id=9, name="OTHER")
    original_creator = User(id=3, email="salam@example.com", full_name="Salam Nassar", role="finance")
    db_session.add_all([entity, project, original_creator])
    db_session.commit()
    return db_session


def test_valid_record_is_ready_with_id_never_forced(target_db):
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(), target, fallback_created_by=None)

    assert result.status == "ready"
    assert result.reject_reasons == []
    assert "id" not in result.insert_kwargs


def test_ready_record_always_gets_restored_expense_nature(target_db):
    """The archive predates expense_nature entirely, so it must always be
    set to 'invoice' regardless of anything in the source record."""
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(), target, fallback_created_by=None)
    assert result.insert_kwargs["expense_nature"] == RESTORED_EXPENSE_NATURE


def test_apply_preserves_occurrence_count_and_next_due_date(target_db):
    """This is the exact behaviour the normal recurring-invoice creation
    service would get wrong — it always resets occurrence_count to 0 and
    recomputes next_due_date. The restore path must not do that."""
    target = load_target_state(target_db)
    record = make_archive_record(occurrence_count=3, next_due_date="2026-01-01")
    result = evaluate_record(1, record, target, fallback_created_by=None)
    assert result.status == "ready"

    target_db.add(RecurringInvoice(**result.insert_kwargs))
    target_db.commit()

    restored = target_db.query(RecurringInvoice).filter(RecurringInvoice.invoice_number_base == "Social Security").one()
    assert restored.occurrence_count == 3
    assert restored.next_due_date == date(2026, 1, 1)


def test_apply_preserves_inactive_state_movo_insurance_case(target_db):
    """Mirrors the archive's real inactive Movo Insurance record — an
    inactive template must stay inactive after restore."""
    target = load_target_state(target_db)
    record = make_archive_record(
        supplier_name_raw="Movo Insurance", invoice_number_base="Direct Debit - Premium Credit Insurance",
        is_active=False,
    )
    result = evaluate_record(1, record, target, fallback_created_by=None)
    assert result.status == "ready"

    target_db.add(RecurringInvoice(**result.insert_kwargs))
    target_db.commit()

    restored = target_db.query(RecurringInvoice).filter(
        RecurringInvoice.supplier_name_raw == "Movo Insurance"
    ).one()
    assert restored.is_active is False


def test_restoring_a_past_due_active_template_never_generates_an_invoice(target_db):
    """The normal service would immediately generate an invoice here since
    next_due_date is in the past and is_active is True. The restore path
    must insert only the template row and touch nothing else."""
    target = load_target_state(target_db)
    record = make_archive_record(is_active=True, next_due_date="2020-01-01", occurrence_count=5)
    result = evaluate_record(1, record, target, fallback_created_by=None)
    assert result.status == "ready"

    target_db.add(RecurringInvoice(**result.insert_kwargs))
    target_db.commit()

    assert target_db.query(Invoice).count() == 0
    restored = target_db.query(RecurringInvoice).one()
    assert restored.occurrence_count == 5
    assert restored.next_due_date == date(2020, 1, 1)


# ── Validation failures ──────────────────────────────────────────────────────

def test_missing_required_field_is_rejected(target_db):
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(supplier_name_raw=""), target, fallback_created_by=None)
    assert result.status == "rejected"
    assert any("supplier_name_raw" in reason for reason in result.reject_reasons)


def test_invalid_frequency_is_rejected(target_db):
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(frequency="fortnightly"), target, fallback_created_by=None)
    assert result.status == "rejected"
    assert any("frequency" in reason for reason in result.reject_reasons)


def test_non_positive_gross_amount_is_rejected(target_db):
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(gross_amount="0"), target, fallback_created_by=None)
    assert result.status == "rejected"


def test_unknown_project_id_is_rejected(target_db):
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(project_id=999), target, fallback_created_by=None)
    assert result.status == "rejected"
    assert any("project" in reason for reason in result.reject_reasons)


def test_unknown_entity_id_is_rejected(target_db):
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(paying_entity_id=999), target, fallback_created_by=None)
    assert result.status == "rejected"
    assert any("entity" in reason for reason in result.reject_reasons)


def test_missing_entity_id_is_allowed_since_field_is_nullable(target_db):
    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(paying_entity_id=None, entity_name=None), target, fallback_created_by=None)
    assert result.status == "ready"
    assert result.insert_kwargs["paying_entity_id"] is None


def test_entity_name_changed_is_a_warning_not_a_rejection(target_db):
    """The id still resolves — a label change (e.g. a legitimate rename)
    shouldn't block restoring the template, just surface for review."""
    target = load_target_state(target_db)
    result = evaluate_record(
        1, make_archive_record(entity_name="Some Old Name Ltd"), target, fallback_created_by=None,
    )
    assert result.status == "ready"
    assert any("entity id 38 name changed" in w for w in result.warnings)


def test_created_by_id_reused_by_a_different_person_is_rejected_without_fallback(target_db):
    """This is the real scenario in the archive: created_by=3 was 'Salam
    Nassar' at export time. If the target's user id 3 is now a different
    person, blindly trusting the numeric id would misattribute the
    restored template to the wrong human."""
    target_db.query(User).filter(User.id == 3).delete()
    target_db.add(User(id=3, email="someone.else@example.com", full_name="Someone Else", role="finance"))
    target_db.commit()

    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(), target, fallback_created_by=None)

    assert result.status == "rejected"
    assert any("created_by" in reason for reason in result.reject_reasons)


def test_created_by_reassigned_uses_fallback_when_supplied(target_db):
    target_db.query(User).filter(User.id == 3).delete()
    target_db.add(User(id=3, email="someone.else@example.com", full_name="Someone Else", role="finance"))
    target_db.add(User(id=99, email="finance-lead@example.com", full_name="Finance Lead", role="admin"))
    target_db.commit()

    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(), target, fallback_created_by=99)

    assert result.status == "ready"
    assert result.insert_kwargs["created_by"] == 99
    assert any("fallback-created-by" in w for w in result.warnings)


def test_missing_created_by_user_entirely_is_rejected_without_fallback(target_db):
    target_db.query(User).filter(User.id == 3).delete()
    target_db.commit()

    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(), target, fallback_created_by=None)
    assert result.status == "rejected"


# ── Duplicate detection ──────────────────────────────────────────────────────

def test_duplicate_candidate_is_skipped_not_inserted(target_db):
    existing = RecurringInvoice(
        supplier_name_raw="Social Security", invoice_number_base="Social Security",
        paying_entity_id=38, project_id=9, gross_amount=Decimal("1"), frequency="monthly",
        start_date=date(2020, 1, 1), next_due_date=date(2020, 2, 1), created_by=3,
    )
    target_db.add(existing)
    target_db.commit()

    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(), target, fallback_created_by=None)

    assert result.status == "duplicate"
    assert result.insert_kwargs is None


def test_same_supplier_different_entity_is_not_a_duplicate(target_db):
    """Mirrors the real archive: three 'BEMO Bank' templates exist, one per
    entity — they must not be treated as duplicates of each other."""
    other_entity = Entity(id=99, name="A Different Entity")
    target_db.add(other_entity)
    target_db.commit()

    existing = RecurringInvoice(
        supplier_name_raw="BEMO Bank", invoice_number_base="BEMO Bank",
        paying_entity_id=99, project_id=9, gross_amount=Decimal("1"), frequency="monthly",
        start_date=date(2020, 1, 1), next_due_date=date(2020, 2, 1), created_by=3,
    )
    target_db.add(existing)
    target_db.commit()

    target = load_target_state(target_db)
    record = make_archive_record(
        supplier_name_raw="BEMO Bank", invoice_number_base="BEMO Bank", paying_entity_id=38,
    )
    result = evaluate_record(1, record, target, fallback_created_by=None)
    assert result.status == "ready"


# ── Preview mode ─────────────────────────────────────────────────────────────

def test_preview_mode_never_writes_to_the_database(target_db, capsys):
    """Evaluating records and printing the preview — everything main() does
    before the --apply gate — must not add, remove, or modify any row."""
    records = [
        make_archive_record(),
        make_archive_record(id=1, supplier_name_raw="Movo Insurance",
                             invoice_number_base="Direct Debit - Premium Credit Insurance", is_active=False),
        make_archive_record(id=99, project_id=999),  # a rejected record too
    ]
    before_recurring = target_db.query(RecurringInvoice).count()
    before_invoices = target_db.query(Invoice).count()

    target = load_target_state(target_db)
    results = [evaluate_record(i, r, target, fallback_created_by=None) for i, r in enumerate(records, start=1)]
    print_preview(records, results, "fake-archive.json")

    captured = capsys.readouterr()
    assert "RECURRING TEMPLATE RESTORE PREVIEW" in captured.out
    assert "Ready to import: 2 of 3 (0 duplicate, 1 rejected)" in captured.out
    assert target_db.query(RecurringInvoice).count() == before_recurring
    assert target_db.query(Invoice).count() == before_invoices


def test_preview_reports_active_and_inactive_counts(target_db, capsys):
    records = [
        make_archive_record(is_active=True),
        make_archive_record(id=1, invoice_number_base="Other 1", is_active=False),
        make_archive_record(id=2, invoice_number_base="Other 2", is_active=False),
    ]
    target = load_target_state(target_db)
    results = [evaluate_record(i, r, target, fallback_created_by=None) for i, r in enumerate(records, start=1)]
    print_preview(records, results, "fake-archive.json")

    captured = capsys.readouterr()
    assert "Source template count: 3" in captured.out
    assert "active:   1" in captured.out
    assert "inactive: 2" in captured.out


def test_duplicate_match_is_case_and_whitespace_insensitive(target_db):
    existing = RecurringInvoice(
        supplier_name_raw="  social security  ", invoice_number_base="SOCIAL SECURITY",
        paying_entity_id=38, project_id=9, gross_amount=Decimal("1"), frequency="monthly",
        start_date=date(2020, 1, 1), next_due_date=date(2020, 2, 1), created_by=3,
    )
    target_db.add(existing)
    target_db.commit()

    target = load_target_state(target_db)
    result = evaluate_record(1, make_archive_record(), target, fallback_created_by=None)
    assert result.status == "duplicate"


# ── Transaction safety: apply must use a fresh session, never the read
# session, so it can never collide with an already-open read transaction. ──

def test_reusing_the_read_session_for_apply_reproduces_the_known_failure(target_db):
    """Pins the exact failure this fix avoids. The preview/validation reads
    auto-begin a transaction on the session; calling `with db.begin()` on
    that SAME session afterward is what previously raised
    "InvalidRequestError: A transaction is already begun on this Session"
    (the same class of bug already hit and fixed in reset_invoice_domain.py).
    This test documents that the failure is real, so nobody "simplifies"
    apply_ready_records() back into reusing the read session."""
    load_target_state(target_db)  # auto-begins an implicit transaction

    with pytest.raises(InvalidRequestError, match="already begun"):
        with target_db.begin():
            pass


def test_apply_uses_a_fresh_session_and_does_not_raise_even_with_an_open_read_transaction(target_db, monkeypatch):
    """The real regression test: run the normal preview/validation queries
    on one session, deliberately leave its transaction open (no rollback,
    no close), then run apply — using the actual SessionLocal-based
    apply_ready_records() function, not a hand-rolled substitute. It must
    not raise, and the row must land with occurrence_count/next_due_date
    preserved exactly, inside one atomic transaction."""
    import scripts.restore_recurring_templates as restore_module

    engine = target_db.get_bind()
    test_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(restore_module, "SessionLocal", test_session_factory)

    read_db = test_session_factory()
    try:
        results = run_preview(read_db, [make_archive_record()], fallback_created_by=None)
        assert results[0].status == "ready"
        # read_db is intentionally left with its implicit transaction still
        # open here — apply_ready_records() must not depend on it being
        # rolled back or closed first.

        ready = [r for r in results if r.status == "ready"]
        apply_ready_records(ready)  # must not raise InvalidRequestError
    finally:
        read_db.close()

    verify_db = test_session_factory()
    try:
        restored = verify_db.query(RecurringInvoice).filter(
            RecurringInvoice.invoice_number_base == "Social Security"
        ).one()
        assert restored.occurrence_count == 3
        assert restored.next_due_date == date(2026, 1, 1)
        assert restored.expense_nature == RESTORED_EXPENSE_NATURE
    finally:
        verify_db.close()


def test_apply_ready_records_is_all_or_nothing(target_db, monkeypatch):
    """If any insert in the batch fails, none of the batch should persist —
    the transaction must be atomic, not per-record."""
    import scripts.restore_recurring_templates as restore_module

    engine = target_db.get_bind()
    test_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(restore_module, "SessionLocal", test_session_factory)

    target = load_target_state(target_db)
    good = evaluate_record(1, make_archive_record(), target, fallback_created_by=None)
    assert good.status == "ready"

    bad = evaluate_record(2, make_archive_record(), target, fallback_created_by=None)
    assert bad.status == "ready"
    bad.insert_kwargs["project_id"] = None  # violates the NOT NULL constraint at insert time

    with pytest.raises(Exception):
        apply_ready_records([good, bad])

    verify_db = test_session_factory()
    try:
        assert verify_db.query(RecurringInvoice).count() == 0
    finally:
        verify_db.close()
