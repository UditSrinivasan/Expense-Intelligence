from datetime import date, timedelta
from decimal import Decimal

from expense_intelligence.models import Transaction, TransactionDirection, TransactionType

HEADERS = {"X-Dev-User-Id": "00000000-0000-4000-8000-000000000071"}
OTHER = {"X-Dev-User-Id": "00000000-0000-4000-8000-000000000072"}


def _seed(client, db):
    client.get("/v1/preferences", headers=HEADERS)
    from expense_intelligence.models import User
    user = db.query(User).filter_by(auth_subject="dev:00000000-0000-4000-8000-000000000071").one()
    start = date(2026, 1, 1)
    rows = []
    for index in range(8):
        rows.append(Transaction(owner_user_id=user.id, description=f"Normal shop {index}", normalized_description="normal shop",
            category="Groceries", transaction_type=TransactionType.purchase, direction=TransactionDirection.expense,
            original_amount=Decimal("100"), original_currency="INR", effective_date=start + timedelta(days=index * 10), needs_review=False))
    for month in range(4):
        rows.append(Transaction(owner_user_id=user.id, description="Rent", normalized_description="rent", category="Housing",
            transaction_type=TransactionType.purchase, direction=TransactionDirection.expense, original_amount=Decimal("1000"),
            original_currency="GBP", effective_date=date(2026, month + 1, 5), needs_review=False))
    rows.extend([
        Transaction(owner_user_id=user.id, description="Laptop", normalized_description="laptop", category="Shopping", transaction_type=TransactionType.purchase, direction=TransactionDirection.expense, original_amount=Decimal("1000"), original_currency="INR", effective_date=date(2026, 4, 10), needs_review=False),
        Transaction(owner_user_id=user.id, description="Cafe", normalized_description="cafe", category="Dining", transaction_type=TransactionType.purchase, direction=TransactionDirection.expense, original_amount=Decimal("250"), original_currency="INR", effective_date=date(2026, 4, 12), needs_review=False),
        Transaction(owner_user_id=user.id, description="Cafe", normalized_description="cafe", category="Dining", transaction_type=TransactionType.purchase, direction=TransactionDirection.expense, original_amount=Decimal("250"), original_currency="INR", effective_date=date(2026, 4, 12), needs_review=False),
        Transaction(owner_user_id=user.id, description="Refund", category="Shopping", transaction_type=TransactionType.refund, direction=TransactionDirection.income, original_amount=Decimal("50"), original_currency="INR", effective_date=date(2026, 4, 13), needs_review=False),
        Transaction(owner_user_id=user.id, description="Card payment", category="Transfer", transaction_type=TransactionType.credit_card_repayment, direction=TransactionDirection.transfer, original_amount=Decimal("9999"), original_currency="INR", effective_date=date(2026, 4, 14), needs_review=False),
    ])
    db.add_all(rows); db.commit()


def test_exact_aggregation_detection_and_currency_separation(client, db):
    _seed(client, db)
    response = client.get("/v1/analytics/overview?start=2026-04-01&end=2026-04-30", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    totals = {row["currency"]: row for row in data["totals"]}
    assert totals["INR"]["spend"] == "1450.00"  # 1000 + 250 + 250 - 50
    assert totals["INR"]["cash_outflow"] == "1450.00"
    assert totals["INR"]["cash_net"] == "-1450.00"
    assert totals["GBP"]["spend"] == "1000.00"
    assert "never combined" in data["fx_policy"]
    assert {row["type"] for row in data["insights"]} == {"unusual_amount", "possible_duplicate"}
    assert data["history"]["unusual_amount"] is True
    assert any(row["merchant"] == "Rent" and row["frequency"] == "monthly" for row in data["recurring"])
    assert data["recent_transactions"][0]["description"] == "Card payment"
    assert data["recent_transactions"][0]["type"] == "credit_card_repayment"


def test_feedback_and_recurring_decisions_are_owner_scoped(client, db):
    _seed(client, db)
    data = client.get("/v1/analytics/overview?start=2026-04-01&end=2026-04-30", headers=HEADERS).json()
    insight = data["insights"][0]
    recurring = data["recurring"][0]
    assert client.put(f"/v1/insights/{insight['id']}", headers=OTHER, json={"feedback": "helpful"}).status_code == 404
    updated = client.put(f"/v1/insights/{insight['id']}", headers=HEADERS, json={"feedback": "helpful", "status": "dismissed"})
    assert updated.json()["feedback"] == "helpful"
    assert client.put(f"/v1/analytics/recurring/{recurring['series_key']}", headers=HEADERS, json={"status": "confirmed", "label": "Flat rent"}).status_code == 200
    refreshed = client.get("/v1/analytics/overview?start=2026-04-01&end=2026-04-30", headers=HEADERS).json()
    assert refreshed["recurring"][0]["status"] == "confirmed"
    assert all(row["id"] != insight["id"] for row in refreshed["insights"])


def test_sparse_data_exposes_insufficient_history(client):
    response = client.get("/v1/analytics/overview?start=2026-01-01&end=2026-01-31", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["history"]["unusual_amount"] is False


def test_invalid_range_is_rejected(client):
    assert client.get("/v1/analytics/overview?start=2026-02-01&end=2026-01-01", headers=HEADERS).status_code == 422
