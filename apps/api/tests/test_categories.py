from decimal import Decimal

from expense_intelligence.models import TransactionAllocation


USER_A = "00000000-0000-4000-8000-000000000011"
USER_B = "00000000-0000-4000-8000-000000000012"


def auth(user: str) -> dict[str, str]:
    return {"X-Dev-User-Id": user}


def transaction(description: str, amount: str = "45.00", direction: str = "expense", transaction_type: str = "purchase"):
    return {"description": description, "category": "Other", "direction": direction, "transaction_type": transaction_type, "original_amount": amount, "original_currency": "GBP", "effective_date": "2026-10-17"}


def category_map(client, user=USER_A):
    return {row["name"]: row for row in client.get("/v1/categories", headers=auth(user)).json()}


def test_taxonomy_custom_categories_and_cross_user_isolation(client):
    categories = category_map(client)
    assert categories["Groceries"]["parent_id"] == categories["Food & Drink"]["id"]
    created = client.post("/v1/categories", headers=auth(USER_A), json={"name": "Pet Care", "parent_id": categories["Miscellaneous"]["id"]})
    assert created.status_code == 201
    assert created.json()["owner_user_id"] is not None
    updated = client.put(f"/v1/categories/{created.json()['id']}", headers=auth(USER_A), json={"name": "Pets"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Pets"
    assert updated.json()["version"] == 2
    assert "Pet Care" not in category_map(client, USER_B)


def test_mixed_allocations_reconcile_and_parent_rollup_without_double_counting(client, db):
    categories = category_map(client)
    created = client.post("/v1/transactions", headers=auth(USER_A), json=transaction("Market receipt")).json()
    response = client.put(f"/v1/transactions/{created['id']}/categorization", headers=auth(USER_A), json={"allocations": [
        {"category_id": categories["Groceries"]["id"], "amount": "25.00"},
        {"category_id": categories["Alcohol"]["id"], "amount": "12.00"},
        {"category_id": categories["Household Items"]["id"], "amount": "8.00"},
    ]})
    assert response.status_code == 200
    assert db.query(TransactionAllocation).filter_by(current=True).count() == 3
    report = client.get("/v1/reports/category-spend?start=2026-10-01&end=2026-10-31&currency=GBP", headers=auth(USER_A)).json()
    totals = {row["name"]: Decimal(row["amount"]) for row in report}
    assert totals["Food & Drink"] == Decimal("37")
    assert totals["Shopping"] == Decimal("8")
    assert totals["Groceries"] + totals["Alcohol"] + totals["Household Items"] == Decimal("45")


def test_allocation_must_reconcile_exactly(client):
    categories = category_map(client)
    created = client.post("/v1/transactions", headers=auth(USER_A), json=transaction("Bad split")).json()
    response = client.put(f"/v1/transactions/{created['id']}/categorization", headers=auth(USER_A), json={"allocations": [{"category_id": categories["Groceries"]["id"], "amount": "44.99"}]})
    assert response.status_code == 422
    assert "exactly equal" in response.json()["detail"]


def test_approved_exact_rule_applies_only_to_owner_and_future_transactions(client):
    categories = category_map(client)
    first = client.post("/v1/transactions", headers=auth(USER_A), json=transaction("ABC Stores UPI")).json()
    corrected = client.put(f"/v1/transactions/{first['id']}/categorization", headers=auth(USER_A), json={"allocations": [{"category_id": categories["Tobacco / Cigarettes"]["id"], "amount": "45.00"}], "create_future_rule": True})
    assert corrected.status_code == 200
    future = client.post("/v1/transactions", headers=auth(USER_A), json=transaction("  ABC Stores UPI  ")).json()
    assert future["category"] == "Tobacco / Cigarettes"
    assert future["classification_source"] == "user_rule"
    other_user = client.post("/v1/transactions", headers=auth(USER_B), json=transaction("ABC Stores UPI")).json()
    assert other_user["classification_source"] == "unclassified"


def test_transfer_is_excluded_from_spending(client):
    client.post("/v1/transactions", headers=auth(USER_A), json=transaction("Move to savings", "100.00", "transfer", "transfer"))
    summary = client.get("/v1/dashboard?currency=GBP", headers=auth(USER_A)).json()
    assert Decimal(summary["expenses"]) == 0


def test_bulk_correction_previews_then_applies_atomically(client):
    categories = category_map(client)
    first = client.post("/v1/transactions", headers=auth(USER_A), json=transaction("Corner shop", "10.00")).json()
    second = client.post("/v1/transactions", headers=auth(USER_A), json=transaction("Local market", "15.50")).json()
    payload = {"transaction_ids": [first["id"], second["id"]], "category_id": categories["Groceries"]["id"]}
    preview = client.post("/v1/transactions/bulk-categorization/preview", headers=auth(USER_A), json=payload)
    assert preview.status_code == 200
    assert Decimal(preview.json()["totals_by_currency"]["GBP"]) == Decimal("25.50")
    assert preview.json()["rejected"] == {}
    applied = client.post("/v1/transactions/bulk-categorization/apply", headers=auth(USER_A), json=payload)
    assert applied.status_code == 200
    assert applied.json()["updated"] == 2
    assert all(row["category"] == "Groceries" for row in client.get("/v1/transactions", headers=auth(USER_A)).json()[:2])


def test_bulk_preview_rejects_cross_user_transaction(client):
    categories = category_map(client)
    foreign = client.post("/v1/transactions", headers=auth(USER_B), json=transaction("Private purchase", "8.00")).json()
    payload = {"transaction_ids": [foreign["id"]], "category_id": categories["Groceries"]["id"]}
    preview = client.post("/v1/transactions/bulk-categorization/preview", headers=auth(USER_A), json=payload).json()
    assert preview["eligible_transaction_ids"] == []
    assert preview["rejected"][foreign["id"]] == "Transaction not found"
    assert client.post("/v1/transactions/bulk-categorization/apply", headers=auth(USER_A), json=payload).status_code == 422
