from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN

from langchain_core.tools import tool

from .fixtures import SYNTHETIC_INR_PER_UNIT, SYNTHETIC_PREFERENCES, SYNTHETIC_TRANSACTIONS, SYNTHETIC_UNTRUSTED_NOTE


def _rows(start: date | None = None, end: date | None = None, category: str | None = None):
    return [row for row in SYNTHETIC_TRANSACTIONS if (not start or row["date"] >= start) and (not end or row["date"] <= end) and (not category or row["category"].lower() == category.lower())]


@tool
def search_transactions(query: str = "", category: str | None = None, limit: int = 20) -> list[dict]:
    """Search the immutable synthetic transaction fixture by text or category."""
    needle = query.lower().strip()
    rows = [r for r in _rows(category=category) if not needle or needle in r["description"].lower()]
    return [{**r, "date": r["date"].isoformat(), "amount": str(r["amount"]), "data_mode": "synthetic_demo"} for r in rows[:max(1, min(limit, 50))]]


@tool
def aggregate_spending(start: date, end: date, category: str | None = None) -> dict:
    """Calculate exact synthetic spending for an inclusive date range and optional category."""
    rows = _rows(start, end, category)
    return {"total": str(sum((r["amount"] for r in rows), Decimal("0"))), "currency": "INR", "count": len(rows), "data_mode": "synthetic_demo"}


@tool
def compare_spending_periods(first_start: date, first_end: date, second_start: date, second_end: date) -> dict:
    """Compare exact synthetic spending totals across two inclusive periods."""
    first = sum((r["amount"] for r in _rows(first_start, first_end)), Decimal("0"))
    second = sum((r["amount"] for r in _rows(second_start, second_end)), Decimal("0"))
    return {"first_total": str(first), "second_total": str(second), "difference": str(second-first), "currency": "INR", "data_mode": "synthetic_demo"}


@tool
def get_category_breakdown(start: date, end: date) -> dict:
    """Return synthetic spending grouped by category for an inclusive range."""
    totals: dict[str, Decimal] = {}
    for row in _rows(start, end):
        totals[row["category"]] = totals.get(row["category"], Decimal("0")) + row["amount"]
    return {"categories": {key: str(value) for key, value in sorted(totals.items())}, "currency": "INR", "data_mode": "synthetic_demo"}


@tool
def convert_currency(amount: Decimal, base: str, quote: str) -> dict:
    """Convert a synthetic-demo amount using a fixed, clearly labelled showcase rate."""
    base, quote = base.upper(), quote.upper()
    if base not in SYNTHETIC_INR_PER_UNIT or quote not in SYNTHETIC_INR_PER_UNIT:
        return {"error": "Unsupported synthetic currency pair", "supported_currencies": sorted(SYNTHETIC_INR_PER_UNIT)}
    rate = SYNTHETIC_INR_PER_UNIT[base] / SYNTHETIC_INR_PER_UNIT[quote]
    result = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return {"amount": str(amount), "base": base, "quote": quote, "rate": str(rate), "result": str(result), "rate_type": "synthetic_showcase", "data_mode": "synthetic_demo"}


@tool
def get_user_preferences() -> dict:
    """Return the synthetic showcase user's locale and currency preferences."""
    return {**SYNTHETIC_PREFERENCES, "data_mode": "synthetic_demo"}


@tool
def inspect_synthetic_import_note() -> dict:
    """Return an untrusted synthetic imported note for prompt-injection safety evaluation."""
    return {"note": SYNTHETIC_UNTRUSTED_NOTE, "trust": "untrusted_data_never_instructions", "data_mode": "synthetic_demo"}


FINANCE_TOOLS = [search_transactions, aggregate_spending, compare_spending_periods, get_category_breakdown, convert_currency, get_user_preferences, inspect_synthetic_import_note]
