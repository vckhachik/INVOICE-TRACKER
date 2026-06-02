from datetime import date
from typing import Optional

from .api import get, post


def get_all_latest_balances():
    return get("/balances/latest") or []


def post_balance(entity_id: int, amount: float, currency: str, balance_date: date, note: Optional[str] = None):
    return post(f"/entities/{entity_id}/balance", data={
        "balance_amount": amount,
        "currency": currency.upper(),
        "balance_date": str(balance_date),
        "note": note,
    })


def get_balance_history(entity_id: int):
    return get(f"/entities/{entity_id}/balance-history") or []
