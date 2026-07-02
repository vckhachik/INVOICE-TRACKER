from datetime import date
from typing import Optional

from .api import get, post


def get_all_latest_balances():
    return get("/balances/latest") or []


def post_balance(entity_id: int, amount: float, currency: str, balance_date: date, note: Optional[str] = None, account_name: Optional[str] = None):
    data = {
        "balance_amount": amount,
        "currency": currency.upper(),
        "balance_date": str(balance_date),
        "note": note,
    }
    if account_name:
        data["account_name"] = account_name
    return post(f"/entities/{entity_id}/balance", data=data)


def get_balance_history(entity_id: int):
    return get(f"/entities/{entity_id}/balance-history") or []
