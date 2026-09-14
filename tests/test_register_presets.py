"""Tests for the Register's status-preset mapping and the "Order by"
selector's mapping onto the backend's existing allowlisted sort fields.
No Streamlit runtime involved — these test the plain functions/dicts that
back the widgets."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from views.invoices import ORDER_BY_OPTIONS, STATUS_PRESETS, _status_preset_filters


# ── Status presets ───────────────────────────────────────────────────────────

def test_all_preset_applies_no_filters():
    assert _status_preset_filters("All") == (None, None, None)


def test_needs_ocr_check_preset_forces_review_status_needs_review():
    is_paid, is_approved, review_status = _status_preset_filters("Needs OCR check")
    assert is_paid is None
    assert is_approved is None
    assert review_status == "needs_review"


def test_awaiting_approval_preset_is_unpaid_and_not_approved():
    assert _status_preset_filters("Awaiting approval") == (False, False, None)


def test_approved_unpaid_preset_is_approved_and_unpaid():
    assert _status_preset_filters("Approved, unpaid") == (False, True, None)


def test_paid_preset_only_constrains_payment():
    is_paid, is_approved, review_status = _status_preset_filters("Paid")
    assert is_paid is True
    assert is_approved is None  # "Paid" doesn't imply anything about approval
    assert review_status is None


def test_unknown_preset_falls_back_to_no_filters():
    assert _status_preset_filters("Something else") == (None, None, None)


def test_status_presets_are_exactly_the_five_specified_labels():
    assert STATUS_PRESETS == ["All", "Needs OCR check", "Awaiting approval", "Approved, unpaid", "Paid"]


def test_presets_are_mutually_distinguishable():
    """Every preset must produce a distinct (is_paid, is_approved, review_status)
    triple — if two presets ever mapped to the same filters, one would be a
    dead, confusing option in the UI."""
    results = [_status_preset_filters(p) for p in STATUS_PRESETS]
    assert len(results) == len(set(results))


# ── Order by ─────────────────────────────────────────────────────────────────

def test_order_by_has_exactly_the_six_specified_options():
    assert set(ORDER_BY_OPTIONS.keys()) == {
        "Newest invoice date", "Oldest invoice date",
        "Highest gross amount", "Lowest gross amount",
        "Supplier A–Z", "Project A–Z",
    }


def test_order_by_options_use_only_backend_allowlisted_sort_fields():
    """The backend's get_invoices only accepts sort_by values in SORT_FIELDS
    and sort_dir in {"asc", "desc"} — every Order-by option must map onto
    that existing allowlist, since backend sort logic is not being changed."""
    from app.api.invoices import SORT_FIELDS

    for label, (sort_by, sort_dir) in ORDER_BY_OPTIONS.items():
        assert sort_by in SORT_FIELDS, f"{label!r} maps to unsupported sort_by={sort_by!r}"
        assert sort_dir in ("asc", "desc"), f"{label!r} has invalid sort_dir={sort_dir!r}"


def test_order_by_directions_are_sensible_opposites():
    assert ORDER_BY_OPTIONS["Newest invoice date"] == ("invoice_date", "desc")
    assert ORDER_BY_OPTIONS["Oldest invoice date"] == ("invoice_date", "asc")
    assert ORDER_BY_OPTIONS["Highest gross amount"] == ("gross_amount", "desc")
    assert ORDER_BY_OPTIONS["Lowest gross amount"] == ("gross_amount", "asc")
