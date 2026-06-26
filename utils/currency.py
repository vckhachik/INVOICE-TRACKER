SUPPORTED_CURRENCIES = ["GBP", "EUR", "USD", "SAR", "AED", "CHF", "LBP"]

CURRENCY_SYMBOLS = {
    "GBP": "£",
    "EUR": "€",
    "USD": "$",
    "SAR": "﷼",
    "AED": "د.إ",
    "CHF": "CHF ",
    "LBP": "LL ",
}

# Rough fallbacks when no DB rate exists — rates expressed as [1 unit → GBP]
DEFAULT_RATE_MAP = {
    "GBP": 1.0,
    "EUR": 0.88,
    "USD": 0.79,
    "SAR": 0.21,
    "AED": 0.22,
    "CHF": 0.90,
    "LBP": 0.0000083,   # ~120,000 LBP/GBP — set the real rate in FX Settings
}


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_rate_map(rates):
    """Build a {currency: rate_to_GBP} dict from /fx/rates/ response."""
    if not rates:
        return DEFAULT_RATE_MAP.copy()
    rate_map = {"GBP": 1.0}
    for rate in rates:
        currency = (rate.get("from_currency") or "").upper().strip()
        if currency:
            rate_map[currency] = safe_float(rate.get("rate"))
    for currency, value in DEFAULT_RATE_MAP.items():
        rate_map.setdefault(currency, value)
    return rate_map


def convert_amount(amount, invoice_currency, display_currency, rate_map):
    """Convert amount from invoice_currency to display_currency via GBP as pivot."""
    amount = safe_float(amount)
    invoice_currency = (invoice_currency or "GBP").upper()
    display_currency = (display_currency or "GBP").upper()
    if invoice_currency == display_currency:
        return amount
    if invoice_currency == "GBP":
        rate_to = rate_map.get(display_currency)
        return amount / rate_to if rate_to else amount
    if display_currency == "GBP":
        rate_from = rate_map.get(invoice_currency)
        return amount * rate_from if rate_from else amount
    rate_from = rate_map.get(invoice_currency)
    rate_to = rate_map.get(display_currency)
    if rate_from and rate_to:
        return amount * rate_from / rate_to
    return amount


def format_native(amount, currency: str) -> str:
    """Format amount in its own currency: 'USD 1,500.00'"""
    if amount is None:
        return "-"
    symbol = CURRENCY_SYMBOLS.get((currency or "GBP").upper(), f"{currency} ")
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return str(amount)


def format_converted(amount, display_currency: str) -> str:
    """Format a pre-converted amount with its display currency symbol."""
    if amount is None:
        return "-"
    symbol = CURRENCY_SYMBOLS.get((display_currency or "GBP").upper(), f"{display_currency} ")
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return str(amount)
