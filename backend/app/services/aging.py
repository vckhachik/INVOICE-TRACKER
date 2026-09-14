"""Invoice aging: single source of truth for bucket boundaries.

Aging is computed from the invoice date and the application server's current
date (not stored on the row). The same bucket table drives both the display
value returned to clients and the WHERE-clause translation used for
server-side filtering, so the two can never disagree at a boundary.
"""
from datetime import date, timedelta
from typing import Optional, Tuple

NOT_DATED = "Not dated"
FUTURE_DATED = "Future dated"

# (label, min_days, max_days) — max_days=None means unbounded.
#
# Finance's wording ("1-30 / 31-60 / 61-90 / 90+") literally overlaps at day
# 90 (it's the top of "61-90" and, read loosely, could also be "90+"). The
# resolved rule, exact and non-overlapping:
#   1-30  = 0  through 30 days old (an invoice dated today is "1-30", not
#           a special case — day 0 is the low end of this band by definition)
#   31-60 = 31 through 60 days old
#   61-90 = 61 through 90 days old
#   90+   = 91 days old ONWARD (the displayed label stays "90+"; the day it
#           actually starts at is 91, not 90 — that's what removes the
#           overlap). See test_90_plus_label_begins_at_day_91.
AGING_BUCKETS = [
    ("1-30", 0, 30),
    ("31-60", 31, 60),
    ("61-90", 61, 90),
    ("90+", 91, None),
]

ALL_BUCKET_LABELS = [b[0] for b in AGING_BUCKETS] + [NOT_DATED, FUTURE_DATED]


def compute_aging(invoice_date: Optional[date], today: Optional[date] = None) -> Tuple[Optional[int], str]:
    """Return (aging_days, aging_bucket) for a given invoice date."""
    if invoice_date is None:
        return None, NOT_DATED

    if today is None:
        today = date.today()

    aging_days = (today - invoice_date).days

    if aging_days < 0:
        return aging_days, FUTURE_DATED

    for label, lo, hi in AGING_BUCKETS:
        if aging_days >= lo and (hi is None or aging_days <= hi):
            return aging_days, label

    # Unreachable: the bucket table above is contiguous and unbounded above,
    # so every aging_days >= 0 matches a bucket.
    raise AssertionError(f"aging_days={aging_days} matched no bucket")


def bucket_date_range(bucket: str, today: Optional[date] = None) -> Tuple[Optional[date], Optional[date]]:
    """Translate a bucket label into an inclusive (min_date, max_date) range
    for filtering `invoice_date`. Returns (None, None) for buckets that
    aren't expressed as a date range (Not dated / Future dated) — callers
    must special-case those directly on nullness / today.
    """
    if today is None:
        today = date.today()

    for label, lo, hi in AGING_BUCKETS:
        if bucket == label:
            max_date = today - timedelta(days=lo)
            min_date = (today - timedelta(days=hi)) if hi is not None else None
            return min_date, max_date

    return None, None
