from datetime import date
from config import CURRENCY_SYMBOLS


def safe_float(value, default=0.0):
    """Convert LLM output like '₹4,500' or 4500 into a float."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    try:
        return float(cleaned)
    except ValueError:
        return default


def fmt_money(amount, currency="INR"):
    sym = CURRENCY_SYMBOLS.get(currency, currency + " ")
    return f"{sym}{amount:,.0f}"


def parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
