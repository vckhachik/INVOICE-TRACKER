from datetime import date, timedelta

import pytest

from app.services.aging import (
    AGING_BUCKETS,
    FUTURE_DATED,
    NOT_DATED,
    bucket_date_range,
    compute_aging,
)

TODAY = date(2026, 9, 14)


def dated(days_ago: int) -> date:
    return TODAY - timedelta(days=days_ago)


def test_missing_invoice_date_is_not_dated():
    aging_days, bucket = compute_aging(None, today=TODAY)
    assert aging_days is None
    assert bucket == NOT_DATED


def test_future_invoice_date_is_future_dated():
    aging_days, bucket = compute_aging(TODAY + timedelta(days=5), today=TODAY)
    assert aging_days == -5
    assert bucket == FUTURE_DATED


def test_invoice_dated_today_is_zero_days_old_and_in_1_30():
    """Day 0 (dated today) is the low end of "1-30" by definition, not a
    fallback case — an invoice becomes visible in the register the moment
    it's dated, at age zero."""
    aging_days, bucket = compute_aging(TODAY, today=TODAY)
    assert aging_days == 0
    assert bucket == "1-30"


@pytest.mark.parametrize(
    "days_ago,expected_bucket",
    [
        (0, "1-30"),
        (1, "1-30"),
        (30, "1-30"),
        (31, "31-60"),
        (60, "31-60"),
        (61, "61-90"),
        (90, "61-90"),
        (91, "90+"),
        (365, "90+"),
    ],
)
def test_bucket_boundaries(days_ago, expected_bucket):
    aging_days, bucket = compute_aging(dated(days_ago), today=TODAY)
    assert aging_days == days_ago
    assert bucket == expected_bucket


def test_90_plus_label_begins_at_day_91():
    """Finance's wording ("61-90" and "90+") overlaps at day 90 on paper.
    The resolved, non-overlapping rule: day 90 belongs to "61-90" and the
    "90+" label (displayed as-is) only starts applying at day 91 onward.
    This is the one boundary decision most likely to regress silently if
    someone "fixes" the off-by-one without reading the docstring in
    app/services/aging.py — hence a dedicated test for exactly this."""
    aging_days_90, bucket_90 = compute_aging(dated(90), today=TODAY)
    aging_days_91, bucket_91 = compute_aging(dated(91), today=TODAY)

    assert (aging_days_90, bucket_90) == (90, "61-90")
    assert (aging_days_91, bucket_91) == (91, "90+")


def test_bucket_date_range_round_trips_into_compute_aging():
    """Every day inside a bucket's derived date range must classify back
    into that same bucket — this is what guarantees the filter and the
    display bucket can never disagree at a boundary."""
    for label, lo, hi in AGING_BUCKETS:
        min_date, max_date = bucket_date_range(label, today=TODAY)
        probe_days = [lo, hi] if hi is not None else [lo, lo + 50]
        for days_ago in probe_days:
            _, bucket = compute_aging(dated(days_ago), today=TODAY)
            assert bucket == label, f"day {days_ago} should be in {label}, got {bucket}"
            probe_date = dated(days_ago)
            assert max_date is not None and probe_date <= max_date
            if min_date is not None:
                assert probe_date >= min_date


def test_bucket_date_range_unknown_label_returns_none():
    assert bucket_date_range(NOT_DATED, today=TODAY) == (None, None)
    assert bucket_date_range(FUTURE_DATED, today=TODAY) == (None, None)
