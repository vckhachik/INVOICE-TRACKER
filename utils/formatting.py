from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Optional

CURRENCY_SYMBOLS = {
    "GBP": "£",
    "EUR": "€",
    "USD": "$",
    "SAR": "﷼",
    "AED": "د.إ",
    "CHF": "CHF",
}


def format_currency(value, symbol: str = "£") -> str:
    if value is None:
        return "-"

    try:
        if isinstance(value, Decimal):
            amount = value
        else:
            amount = Decimal(str(value))

        return f"{symbol}{amount:,.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


def format_date(value) -> str:
    if not value:
        return "-"

    try:
        if isinstance(value, (datetime, date)):
            return value.strftime("%Y-%m-%d")

        # Try parsing string
        parsed = datetime.fromisoformat(str(value))
        return parsed.strftime("%Y-%m-%d")

    except Exception:
        return str(value)[:10]


def format_status(value: Optional[bool]) -> str:
    if value is True:
        return "✅"
    if value is False:
        return "❌"
    return "-"


def format_review_status(status: Optional[str]) -> str:
    mapping = {
        "auto_accepted": "✅ Auto Accepted",
        "needs_review": "⚠️ Needs Review",
        "pending": "🕐 Pending",
        "failed": "❌ Failed",
    }
    return mapping.get(status, "-")