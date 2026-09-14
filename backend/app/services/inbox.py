"""Read-only Inbox summary: four queues of invoices that may need a
decision, plus a single distinct "needs action" headline count.

This module never writes to the database. It exists purely to compute the
four queue conditions once and reuse them for both per-queue counts/pages
and the combined distinct-count query, so the two can never drift apart.
"""
from sqlalchemy import and_, or_

from app.models.models import Invoice

PAGE_LIMIT = 10

NEEDS_MANUAL_CHECK_STATUSES = ("needs_review", "failed")


def _needs_manual_check_condition():
    return Invoice.review_status.in_(NEEDS_MANUAL_CHECK_STATUSES)


def _unmapped_condition():
    return or_(Invoice.project_id.is_(None), Invoice.paying_entity_id.is_(None))


def _awaiting_approval_condition():
    return and_(Invoice.is_paid.is_(False), Invoice.is_approved_to_pay.is_(False))


def _approved_unpaid_condition():
    return and_(Invoice.is_approved_to_pay.is_(True), Invoice.is_paid.is_(False))


def _queue(db, condition):
    query = db.query(Invoice).filter(condition)
    total = query.count()
    items = (
        query.order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .limit(PAGE_LIMIT)
        .all()
    )
    return {"total": total, "items": items}


def get_inbox_summary(db) -> dict:
    needs_manual_check = _needs_manual_check_condition()
    unmapped = _unmapped_condition()
    awaiting_approval = _awaiting_approval_condition()
    approved_unpaid = _approved_unpaid_condition()

    # Distinct count across the three "needs a decision" queues in one
    # query — an invoice matching more than one queue (e.g. needs manual
    # check AND unmapped) must be counted once, never summed.
    needs_action_count = (
        db.query(Invoice.id)
        .filter(or_(needs_manual_check, unmapped, awaiting_approval))
        .distinct()
        .count()
    )

    return {
        "needs_action_count": needs_action_count,
        "queues": {
            "needs_manual_check": _queue(db, needs_manual_check),
            "unmapped": _queue(db, unmapped),
            "awaiting_approval": _queue(db, awaiting_approval),
            "approved_unpaid": _queue(db, approved_unpaid),
        },
    }
