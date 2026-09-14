"""Tests for the Dashboard's per-Project "Order invoices by" helper.
order_project_invoices() must be deterministic (id as final tie-breaker) and
must not touch aging (that field is never referenced here at all)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from views.dashboard import INVOICE_ORDER_OPTIONS, order_project_invoices


def make_invoice(id, invoice_date=None, gross_amount=0, supplier_name_raw="",
                  is_paid=False, is_approved_to_pay=False):
    return {
        "id": id,
        "invoice_date": invoice_date,
        "gross_amount": gross_amount,
        "supplier_name_raw": supplier_name_raw,
        "is_paid": is_paid,
        "is_approved_to_pay": is_approved_to_pay,
    }


def ids(invoices):
    return [inv["id"] for inv in invoices]


# ── Date ordering ────────────────────────────────────────────────────────────

def test_newest_invoice_date_first():
    invoices = [
        make_invoice(1, invoice_date="2026-01-01"),
        make_invoice(2, invoice_date="2026-03-01"),
        make_invoice(3, invoice_date="2026-02-01"),
    ]
    result = order_project_invoices(invoices, "Newest invoice date")
    assert ids(result) == [2, 3, 1]


def test_oldest_invoice_date_first():
    invoices = [
        make_invoice(1, invoice_date="2026-01-01"),
        make_invoice(2, invoice_date="2026-03-01"),
        make_invoice(3, invoice_date="2026-02-01"),
    ]
    result = order_project_invoices(invoices, "Oldest invoice date")
    assert ids(result) == [1, 3, 2]


def test_undated_invoices_sort_last_in_both_date_directions():
    invoices = [
        make_invoice(1, invoice_date=None),
        make_invoice(2, invoice_date="2026-01-01"),
        make_invoice(3, invoice_date=None),
    ]
    newest = order_project_invoices(invoices, "Newest invoice date")
    oldest = order_project_invoices(invoices, "Oldest invoice date")
    assert ids(newest) == [2, 1, 3]
    assert ids(oldest) == [2, 1, 3]


def test_default_unrecognized_order_by_falls_back_to_newest_first():
    invoices = [make_invoice(1, invoice_date="2026-01-01"), make_invoice(2, invoice_date="2026-02-01")]
    assert ids(order_project_invoices(invoices, "something unexpected")) == [2, 1]


# ── Amount / supplier ordering ───────────────────────────────────────────────

def test_highest_gross_amount_first():
    invoices = [make_invoice(1, gross_amount=50), make_invoice(2, gross_amount=200), make_invoice(3, gross_amount=100)]
    assert ids(order_project_invoices(invoices, "Highest gross amount")) == [2, 3, 1]


def test_lowest_gross_amount_first():
    invoices = [make_invoice(1, gross_amount=50), make_invoice(2, gross_amount=200), make_invoice(3, gross_amount=100)]
    assert ids(order_project_invoices(invoices, "Lowest gross amount")) == [1, 3, 2]


def test_supplier_a_to_z_is_case_insensitive():
    invoices = [
        make_invoice(1, supplier_name_raw="zeta"),
        make_invoice(2, supplier_name_raw="Alpha"),
        make_invoice(3, supplier_name_raw="beta"),
    ]
    assert ids(order_project_invoices(invoices, "Supplier A–Z")) == [2, 3, 1]


# ── Status-first ordering: group first, then newest date, then id ──────────

def test_approved_to_pay_first_groups_then_sorts_by_newest_date():
    invoices = [
        make_invoice(1, invoice_date="2026-01-01", is_approved_to_pay=False),
        make_invoice(2, invoice_date="2026-03-01", is_approved_to_pay=True),
        make_invoice(3, invoice_date="2026-02-01", is_approved_to_pay=True),
        make_invoice(4, invoice_date="2026-04-01", is_approved_to_pay=False),
    ]
    result = order_project_invoices(invoices, "Approved to pay first")
    # Approved group (2, 3) newest-first, then not-approved group (4, 1) newest-first.
    assert ids(result) == [2, 3, 4, 1]


def test_unpaid_first_groups_then_sorts_by_newest_date():
    invoices = [
        make_invoice(1, invoice_date="2026-01-01", is_paid=True),
        make_invoice(2, invoice_date="2026-03-01", is_paid=False),
        make_invoice(3, invoice_date="2026-02-01", is_paid=False),
    ]
    result = order_project_invoices(invoices, "Unpaid first")
    assert ids(result) == [2, 3, 1]


def test_paid_first_groups_then_sorts_by_newest_date():
    invoices = [
        make_invoice(1, invoice_date="2026-01-01", is_paid=False),
        make_invoice(2, invoice_date="2026-03-01", is_paid=True),
        make_invoice(3, invoice_date="2026-02-01", is_paid=True),
    ]
    result = order_project_invoices(invoices, "Paid first")
    assert ids(result) == [2, 3, 1]


def test_status_first_options_place_undated_last_within_their_group():
    invoices = [
        make_invoice(1, invoice_date=None, is_paid=False),
        make_invoice(2, invoice_date="2026-01-01", is_paid=False),
    ]
    result = order_project_invoices(invoices, "Unpaid first")
    assert ids(result) == [2, 1]


# ── Deterministic id tie-breaking ────────────────────────────────────────────

def test_id_is_final_tiebreak_for_same_date():
    invoices = [
        make_invoice(3, invoice_date="2026-01-01"),
        make_invoice(1, invoice_date="2026-01-01"),
        make_invoice(2, invoice_date="2026-01-01"),
    ]
    assert ids(order_project_invoices(invoices, "Newest invoice date")) == [1, 2, 3]
    assert ids(order_project_invoices(invoices, "Oldest invoice date")) == [1, 2, 3]


def test_id_is_final_tiebreak_for_same_gross_amount():
    invoices = [make_invoice(3, gross_amount=100), make_invoice(1, gross_amount=100), make_invoice(2, gross_amount=100)]
    assert ids(order_project_invoices(invoices, "Highest gross amount")) == [1, 2, 3]
    assert ids(order_project_invoices(invoices, "Lowest gross amount")) == [1, 2, 3]


def test_id_is_final_tiebreak_for_same_supplier():
    invoices = [
        make_invoice(3, supplier_name_raw="Acme"),
        make_invoice(1, supplier_name_raw="Acme"),
        make_invoice(2, supplier_name_raw="Acme"),
    ]
    assert ids(order_project_invoices(invoices, "Supplier A–Z")) == [1, 2, 3]


def test_id_is_final_tiebreak_within_a_status_group_on_same_date():
    invoices = [
        make_invoice(3, invoice_date="2026-01-01", is_paid=False),
        make_invoice(1, invoice_date="2026-01-01", is_paid=False),
        make_invoice(2, invoice_date="2026-01-01", is_paid=False),
    ]
    assert ids(order_project_invoices(invoices, "Unpaid first")) == [1, 2, 3]


def test_ordering_never_changes_the_set_of_invoices_only_their_order():
    invoices = [make_invoice(i, gross_amount=i) for i in range(5)]
    for option in INVOICE_ORDER_OPTIONS:
        result = order_project_invoices(invoices, option)
        assert set(ids(result)) == {0, 1, 2, 3, 4}
        assert len(result) == 5


def test_invoice_order_options_are_exactly_the_eight_specified():
    assert INVOICE_ORDER_OPTIONS == [
        "Newest invoice date", "Oldest invoice date",
        "Highest gross amount", "Lowest gross amount",
        "Supplier A–Z",
        "Approved to pay first", "Unpaid first", "Paid first",
    ]
