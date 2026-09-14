from datetime import date, datetime, timedelta
from decimal import Decimal

from app.api.invoices import get_invoices_inbox
from app.models.models import Invoice, InvoiceActivityLog, InvoiceFile, RecurringInvoice
from app.services.inbox import PAGE_LIMIT, get_inbox_summary


def make_invoice(db, created_at=None, **overrides):
    defaults = dict(
        supplier_name_raw="Acme Ltd",
        invoice_number="INV-1",
        invoice_date=date.today(),
        gross_amount=Decimal("100.00"),
        currency="GBP",
        review_status="auto_accepted",
        project_id=1,
        paying_entity_id=1,
        is_paid=False,
        is_approved_to_pay=False,
    )
    defaults.update(overrides)
    invoice = Invoice(**defaults)
    if created_at is not None:
        invoice.created_at = created_at
    db.add(invoice)
    db.flush()
    return invoice


# ── Needs manual check ───────────────────────────────────────────────────────

def test_needs_manual_check_matches_needs_review_and_failed(db_session):
    needs_review = make_invoice(db_session, review_status="needs_review", invoice_number="A")
    failed = make_invoice(db_session, review_status="failed", invoice_number="B")
    db_session.commit()

    summary = get_inbox_summary(db_session)
    ids = {inv.id for inv in summary["queues"]["needs_manual_check"]["items"]}
    assert ids == {needs_review.id, failed.id}
    assert summary["queues"]["needs_manual_check"]["total"] == 2


def test_needs_manual_check_excludes_other_review_statuses(db_session):
    for status in ("pending", "auto_accepted"):
        make_invoice(db_session, review_status=status, invoice_number=status)
    db_session.commit()

    summary = get_inbox_summary(db_session)
    assert summary["queues"]["needs_manual_check"]["total"] == 0
    assert summary["queues"]["needs_manual_check"]["items"] == []


# ── Unmapped ─────────────────────────────────────────────────────────────────

def test_unmapped_matches_missing_project_or_missing_entity_independently(db_session):
    no_project = make_invoice(db_session, invoice_number="NP", project_id=None, paying_entity_id=1)
    no_entity = make_invoice(db_session, invoice_number="NE", project_id=1, paying_entity_id=None)
    fully_mapped = make_invoice(db_session, invoice_number="OK", project_id=1, paying_entity_id=1)
    db_session.commit()

    summary = get_inbox_summary(db_session)
    ids = {inv.id for inv in summary["queues"]["unmapped"]["items"]}
    assert ids == {no_project.id, no_entity.id}
    assert fully_mapped.id not in ids
    assert summary["queues"]["unmapped"]["total"] == 2


def test_unmapped_counts_missing_both_fields_exactly_once(db_session):
    missing_both = make_invoice(db_session, project_id=None, paying_entity_id=None)
    db_session.commit()

    summary = get_inbox_summary(db_session)
    assert summary["queues"]["unmapped"]["total"] == 1
    assert [inv.id for inv in summary["queues"]["unmapped"]["items"]] == [missing_both.id]


# ── Awaiting approval / Approved unpaid partition ───────────────────────────

def test_awaiting_approval_and_approved_unpaid_are_mutually_exclusive(db_session):
    awaiting = make_invoice(db_session, invoice_number="AWAIT", is_paid=False, is_approved_to_pay=False)
    approved_unpaid = make_invoice(db_session, invoice_number="APPR", is_paid=False, is_approved_to_pay=True)
    paid_approved = make_invoice(db_session, invoice_number="PAID1", is_paid=True, is_approved_to_pay=True)
    paid_unapproved = make_invoice(db_session, invoice_number="PAID2", is_paid=True, is_approved_to_pay=False)
    db_session.commit()

    summary = get_inbox_summary(db_session)
    awaiting_ids = {inv.id for inv in summary["queues"]["awaiting_approval"]["items"]}
    approved_unpaid_ids = {inv.id for inv in summary["queues"]["approved_unpaid"]["items"]}

    assert awaiting_ids == {awaiting.id}
    assert approved_unpaid_ids == {approved_unpaid.id}
    assert paid_approved.id not in awaiting_ids | approved_unpaid_ids
    assert paid_unapproved.id not in awaiting_ids | approved_unpaid_ids


# ── Distinct headline count ──────────────────────────────────────────────────

def test_needs_action_count_is_distinct_not_summed_for_an_overlapping_invoice(db_session):
    """The exact scenario this whole design exists to get right: one
    invoice matching two queues at once must be counted once."""
    overlapping = make_invoice(
        db_session, invoice_number="OVERLAP", review_status="needs_review", project_id=None,
    )
    # Also unmapped AND (by the default is_paid=False/is_approved_to_pay=False)
    # awaiting approval — deliberately touches two of the three queues too.
    double_match = make_invoice(db_session, invoice_number="DOUBLE", project_id=None, paying_entity_id=1)
    no_match = make_invoice(
        db_session, invoice_number="NONE", review_status="auto_accepted",
        project_id=1, paying_entity_id=1, is_paid=True, is_approved_to_pay=True,
    )
    db_session.commit()

    summary = get_inbox_summary(db_session)

    # Per-queue totals here are needs_manual_check=1, unmapped=2,
    # awaiting_approval=2 — a naive sum would be 5. Only two distinct
    # invoices (`overlapping`, `double_match`) touch any of the three
    # queues at all, so the correct distinct count is 2.
    assert summary["queues"]["needs_manual_check"]["total"] == 1
    assert summary["queues"]["unmapped"]["total"] == 2
    assert summary["queues"]["awaiting_approval"]["total"] == 2
    assert summary["needs_action_count"] == 2
    assert no_match.id != overlapping.id
    assert no_match.id != double_match.id


def test_needs_action_count_excludes_approved_unpaid(db_session):
    make_invoice(db_session, is_paid=False, is_approved_to_pay=True,
                 review_status="auto_accepted", project_id=1, paying_entity_id=1)
    db_session.commit()

    summary = get_inbox_summary(db_session)
    assert summary["needs_action_count"] == 0


# ── Queue totals vs. page size ───────────────────────────────────────────────

def test_queue_total_reflects_full_match_count_not_just_the_page(db_session):
    for i in range(PAGE_LIMIT + 5):
        make_invoice(db_session, invoice_number=f"UNMAPPED-{i}", project_id=None)
    db_session.commit()

    summary = get_inbox_summary(db_session)
    assert summary["queues"]["unmapped"]["total"] == PAGE_LIMIT + 5
    assert len(summary["queues"]["unmapped"]["items"]) == PAGE_LIMIT


# ── Ordering ─────────────────────────────────────────────────────────────────

def test_ordering_is_newest_created_first_then_id_descending(db_session):
    now = datetime(2026, 1, 1, 12, 0, 0)
    older = make_invoice(db_session, invoice_number="OLD", project_id=None, created_at=now - timedelta(days=2))
    newer = make_invoice(db_session, invoice_number="NEW", project_id=None, created_at=now)
    tied_a = make_invoice(db_session, invoice_number="TIE-A", project_id=None, created_at=now - timedelta(days=1))
    tied_b = make_invoice(db_session, invoice_number="TIE-B", project_id=None, created_at=now - timedelta(days=1))
    db_session.commit()

    summary = get_inbox_summary(db_session)
    ids_in_order = [inv.id for inv in summary["queues"]["unmapped"]["items"]]

    # newest created_at first ...
    assert ids_in_order[0] == newer.id
    # ... ties on created_at broken by id descending ...
    tie_positions = [ids_in_order.index(tied_b.id), ids_in_order.index(tied_a.id)]
    assert tie_positions == sorted(tie_positions)  # tied_b (higher id) sorts before tied_a
    # ... oldest last.
    assert ids_in_order[-1] == older.id


def test_ordering_is_stable_across_repeated_calls_with_no_data_change(db_session):
    same_time = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(5):
        make_invoice(db_session, invoice_number=f"TIE-{i}", project_id=None, created_at=same_time)
    db_session.commit()

    first_call = [inv.id for inv in get_inbox_summary(db_session)["queues"]["unmapped"]["items"]]
    second_call = [inv.id for inv in get_inbox_summary(db_session)["queues"]["unmapped"]["items"]]
    assert first_call == second_call
    assert first_call == sorted(first_call, reverse=True)  # id descending tie-break


# ── No side effects ──────────────────────────────────────────────────────────

def test_get_inbox_summary_is_purely_read_only(db_session):
    make_invoice(db_session, review_status="needs_review")
    db_session.commit()

    before = {
        "invoices": db_session.query(Invoice).count(),
        "recurring": db_session.query(RecurringInvoice).count(),
        "files": db_session.query(InvoiceFile).count(),
        "activity": db_session.query(InvoiceActivityLog).count(),
    }

    get_inbox_summary(db_session)

    after = {
        "invoices": db_session.query(Invoice).count(),
        "recurring": db_session.query(RecurringInvoice).count(),
        "files": db_session.query(InvoiceFile).count(),
        "activity": db_session.query(InvoiceActivityLog).count(),
    }
    assert before == after


# ── Route-level: visible to every authenticated role ────────────────────────

def test_route_has_no_permission_gate_and_returns_typed_response(db_session, actor):
    make_invoice(
        db_session, review_status="needs_review",
        is_paid=True, is_approved_to_pay=True,  # isolate to needs_manual_check only
    )
    db_session.commit()

    for role in ("partner", "finance", "admin"):
        actor.role = role
        response = get_invoices_inbox(db=db_session, actor=actor)
        assert response.needs_action_count >= 1
        assert response.queues.needs_manual_check.total >= 1
        assert response.queues.unmapped.total == 0
        assert response.queues.awaiting_approval.total == 0
        assert response.queues.approved_unpaid.total == 0
