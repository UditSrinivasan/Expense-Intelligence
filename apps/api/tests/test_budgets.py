from datetime import date
from decimal import Decimal

from expense_intelligence.models import FxRate

USER_A = "00000000-0000-4000-8000-000000000021"
USER_B = "00000000-0000-4000-8000-000000000022"


def auth(user=USER_A):
    return {"X-Dev-User-Id": user}


def categories(client, user=USER_A):
    return {row["name"]: row for row in client.get("/v1/categories", headers=auth(user)).json()}


def add_transaction(client, description, amount, currency="GBP", direction="expense", transaction_type="purchase", on="2026-10-17", user=USER_A):
    payload = {"description": description, "category": "Other", "direction": direction, "transaction_type": transaction_type, "original_amount": amount, "original_currency": currency, "effective_date": on}
    return client.post("/v1/transactions", headers=auth(user), json=payload).json()


def allocate(client, transaction, allocations, user=USER_A):
    return client.put(f"/v1/transactions/{transaction['id']}/categorization", headers=auth(user), json={"allocations": allocations})


def create_budget(client, **overrides):
    payload = {"name": "October budget", "category_id": None, "amount": "100.00", "currency": "GBP", "period_type": "monthly", "start_date": "2026-10-01", "end_date": "2026-10-31", "time_zone": "Europe/London", "warning_percent": "80"}
    payload.update(overrides)
    return client.post("/v1/budgets", headers=auth(), json=payload)


def test_parent_budget_rolls_up_mixed_allocations_without_double_counting(client):
    cats = categories(client)
    receipt = add_transaction(client, "Mixed receipt", "45.00")
    assert allocate(client, receipt, [
        {"category_id": cats["Groceries"]["id"], "amount": "25.00"},
        {"category_id": cats["Alcohol"]["id"], "amount": "12.00"},
        {"category_id": cats["Household Items"]["id"], "amount": "8.00"},
    ]).status_code == 200
    budget = create_budget(client, category_id=cats["Food & Drink"]["id"], amount="50.00").json()
    evaluation = client.get(f"/v1/budgets/{budget['id']}", headers=auth()).json()
    assert Decimal(evaluation["spent"]) == Decimal("37")
    assert Decimal(evaluation["remaining"]) == Decimal("13")
    assert sum(Decimal(item["amount"]) for item in evaluation["largest_subcategories"]) == Decimal("37")


def test_overall_and_overlapping_category_budgets_are_evaluated_independently(client):
    cats = categories(client)
    row = add_transaction(client, "Dinner", "60.00")
    allocate(client, row, [{"category_id": cats["Restaurants"]["id"], "amount": "60.00"}])
    overall = create_budget(client, name="Overall", amount="200.00").json()
    parent = create_budget(client, name="Food", category_id=cats["Food & Drink"]["id"], amount="50.00").json()
    evaluations = {item["budget"]["id"]: item for item in client.get("/v1/budgets", headers=auth()).json()}
    assert Decimal(evaluations[overall["id"]]["spent"]) == Decimal("60")
    assert Decimal(evaluations[parent["id"]]["spent"]) == Decimal("60")
    assert evaluations[parent["id"]]["warning_state"] == "over_budget"


def test_overall_budget_includes_uncategorized_spending_once(client):
    add_transaction(client, "Needs review", "19.75")
    budget = create_budget(client, name="Overall").json()
    result = client.get(f"/v1/budgets/{budget['id']}", headers=auth()).json()
    assert Decimal(result["spent"]) == Decimal("19.75")
    assert result["contributions"][0]["category_id"] is None


def test_refunds_reduce_budget_spend_and_transfers_are_excluded(client):
    cats = categories(client)
    purchase = add_transaction(client, "Shoes", "80.00")
    refund = add_transaction(client, "Shoes refund", "20.00", direction="income", transaction_type="refund")
    transfer = add_transaction(client, "Savings", "500.00", direction="transfer", transaction_type="transfer")
    allocate(client, purchase, [{"category_id": cats["Clothing"]["id"], "amount": "80.00"}])
    assert allocate(client, refund, [{"category_id": cats["Clothing"]["id"], "amount": "20.00"}]).status_code == 200
    budget = create_budget(client, category_id=cats["Shopping"]["id"]).json()
    result = client.get(f"/v1/budgets/{budget['id']}", headers=auth()).json()
    assert Decimal(result["spent"]) == Decimal("60")
    assert all(item["transaction_id"] != transfer["id"] for item in result["contributions"])


def test_historical_fx_and_missing_fx_are_explicit(client, db):
    cats = categories(client)
    converted = add_transaction(client, "Delhi purchase", "1000.00", currency="INR", on="2026-10-17")
    missing = add_transaction(client, "Tokyo purchase", "1000", currency="JPY", on="2026-10-17")
    allocate(client, converted, [{"category_id": cats["Groceries"]["id"], "amount": "1000.00"}])
    allocate(client, missing, [{"category_id": cats["Groceries"]["id"], "amount": "1000"}])
    db.add(FxRate(provider="test-reference", base_currency="INR", quote_currency="GBP", rate=Decimal("0.0095"), rate_date=date(2026, 10, 16), attribution="test fixture")); db.commit()
    budget = create_budget(client, amount="20.00").json()
    result = client.get(f"/v1/budgets/{budget['id']}", headers=auth()).json()
    assert Decimal(result["spent"]) == Decimal("9.50")
    assert result["complete"] is False
    assert Decimal(result["excluded_by_currency"]["JPY"]) == Decimal("1000")
    converted_row = next(item for item in result["contributions"] if item["original_currency"] == "INR")
    assert converted_row["rate_provider"] == "test-reference"
    assert converted_row["rate_date"] == "2026-10-16"


def test_budget_history_archive_concurrency_and_cross_user_isolation(client):
    budget = create_budget(client).json()
    update = client.put(f"/v1/budgets/{budget['id']}", headers=auth(), json={"expected_version": 1, "amount": "120.00", "status": "archived"})
    assert update.status_code == 200 and update.json()["version"] == 2
    assert client.put(f"/v1/budgets/{budget['id']}", headers=auth(), json={"expected_version": 1, "amount": "130.00"}).status_code == 409
    assert len(client.get(f"/v1/budgets/{budget['id']}/history", headers=auth()).json()) == 2
    assert client.get(f"/v1/budgets/{budget['id']}", headers=auth(USER_B)).status_code == 404
    assert client.delete(f"/v1/budgets/{budget['id']}?expected_version=2", headers=auth(USER_B)).status_code == 404
    assert client.delete(f"/v1/budgets/{budget['id']}?expected_version=2", headers=auth()).status_code == 204


def test_period_timezone_and_currency_precision_validation(client):
    assert create_budget(client, time_zone="Not/AZone").status_code == 422
    assert create_budget(client, start_date="2026-10-02").status_code == 422
    jpy = create_budget(client, name="JPY", amount="1000", currency="JPY").json()
    kwd = create_budget(client, name="KWD", amount="10.125", currency="KWD").json()
    assert Decimal(client.get(f"/v1/budgets/{jpy['id']}", headers=auth()).json()["remaining"]) == Decimal("1000")
    assert Decimal(client.get(f"/v1/budgets/{kwd['id']}", headers=auth()).json()["remaining"]) == Decimal("10.125")
