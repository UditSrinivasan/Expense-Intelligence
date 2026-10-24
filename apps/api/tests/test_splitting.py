from datetime import date
from decimal import Decimal
import uuid

import pytest

from expense_intelligence.models import ExpenseAllocation, ExpenseComponent, GroupMember, SharedExpense, Transaction, TransactionDirection, TransactionType, User
from expense_intelligence.splitting import ComponentInput, ShareInput, _allocate


USER_A = "00000000-0000-4000-8000-000000000001"
USER_B = "00000000-0000-4000-8000-000000000002"


def headers(user=USER_A):
    return {"X-Dev-User-Id": user}


def create_group(client):
    response = client.post("/v1/groups", headers=headers(), json={"name": "Goa trip", "default_currency": "INR", "owner_name": "Asha"})
    assert response.status_code == 201
    group = response.json()
    group["members"] = client.get(f"/v1/groups/{group['id']}", headers=headers()).json()["members"]
    return group


def test_largest_remainder_is_exact_and_stable_across_currency_precisions():
    ids = ["00000000-0000-4000-8000-000000000003", "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002"]
    for amount, quantum in [(Decimal("100"), Decimal("1")), (Decimal("10.00"), Decimal("0.01")), (Decimal("1.001"), Decimal("0.001"))]:
        component = ComponentInput(label="Shared", amount=amount, strategy="equal", shares=[ShareInput(member_id=value) for value in ids])
        result = _allocate(component, quantum)
        assert sum(row["amount"] for row in result) == amount
        residual_ids = [str(row["member_id"]) for row in result if row["received_residual"]]
        assert residual_ids == sorted(residual_ids)


def test_group_preview_confirm_balances_and_private_authorization(client, db):
    group = create_group(client)
    owner_id = group["members"][0]["id"]
    guest = client.post(f"/v1/groups/{group['id']}/members", headers=headers(), json={"display_name": "Ben"})
    assert guest.status_code == 201
    guest_id = guest.json()["id"]
    payload = {
        "idempotency_key": "10000000-0000-4000-8000-000000000001", "description": "Dinner and discount", "total": "99.99", "currency": "INR", "expense_date": str(date.today()),
        "payers": [{"member_id": owner_id, "amount": "70.00"}, {"member_id": guest_id, "amount": "29.99"}],
        "components": [
            {"label": "Meals", "amount": "110.00", "strategy": "weighted", "shares": [{"member_id": owner_id, "value": "2"}, {"member_id": guest_id, "value": "1"}]},
            {"label": "Coupon", "amount": "-10.01", "strategy": "equal", "shares": [{"member_id": owner_id}, {"member_id": guest_id}]},
        ],
    }
    preview = client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=payload)
    assert preview.status_code == 200, preview.text
    assert sum(Decimal(row["amount"]) for row in preview.json()["allocations"]) == Decimal("99.99")
    assert sum(Decimal(row["balance"]) for row in preview.json()["balances"]) == 0
    confirmed = client.post(f"/v1/groups/{group['id']}/expenses", headers=headers(), json=payload)
    assert confirmed.status_code == 201, confirmed.text
    assert db.query(SharedExpense).count() == 1
    assert client.post(f"/v1/groups/{group['id']}/expenses", headers=headers(), json=payload).json()["id"] == confirmed.json()["id"]
    assert db.query(SharedExpense).count() == 1
    assert sum(row.amount for row in db.query(ExpenseAllocation).all()) == Decimal("99.990000000000")
    balances = client.get(f"/v1/groups/{group['id']}/balances", headers=headers()).json()
    assert sum(Decimal(row["balance"]) for row in balances) == 0
    assert client.get(f"/v1/groups/{group['id']}", headers=headers(USER_B)).status_code == 404
    assert client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(USER_B), json=payload).status_code == 404


def test_item_scoped_discount_does_not_leak_and_keeps_payers_separate(client):
    group = create_group(client)
    members = group["members"][:]
    for name in ["B", "C", "D", "E", "F", "G"]:
        response = client.post(f"/v1/groups/{group['id']}/members", headers=headers(), json={"display_name": name})
        assert response.status_code == 201
        members.append(response.json())
    ids = [member["id"] for member in members]
    payload = {
        "idempotency_key": "11000000-0000-4000-8000-000000000001",
        "description": "Selective promotion",
        "total": "2600.00",
        "currency": "INR",
        "expense_date": "2026-10-24",
        "payers": [{"member_id": ids[0], "amount": "2600.00"}],
        "components": [
            {"label": "Item X", "kind": "item", "amount": "2000.00", "strategy": "equal", "shares": [{"member_id": ids[index]} for index in [0, 1, 2, 4]]},
            {"label": "Item Y", "kind": "item", "amount": "1000.00", "strategy": "equal", "shares": [{"member_id": ids[index]} for index in [3, 5, 6]]},
            {"label": "X promotion", "kind": "discount", "promotion_id": "x-only", "discount_mode": "fixed", "amount": "-400.00", "eligible_component_indexes": [0], "strategy": "equal", "shares": [{"member_id": ids[index]} for index in [0, 1, 2, 4]]},
        ],
    }
    response = client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    owed = {row["member_id"]: Decimal(row["owed"]) for row in result["balances"]}
    assert [owed[ids[index]] for index in [0, 1, 2, 4]] == [Decimal("400.00")] * 4
    assert sorted(owed[ids[index]] for index in [3, 5, 6]) == [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")]
    assert Decimal(result["components"][2]["basis"]) == Decimal("2000.00")
    assert sum(owed.values()) == Decimal("2600.00")
    assert Decimal(next(row for row in result["balances"] if row["member_id"] == ids[0])["paid"]) == Decimal("2600.00")


def test_percentage_promotions_respect_caps_minimums_and_non_discountable_items(client):
    group = create_group(client); owner_id = group["members"][0]["id"]
    base = {
        "idempotency_key": "11000000-0000-4000-8000-000000000002", "description": "Promotion rules", "total": "135.00", "currency": "GBP", "expense_date": "2026-10-24",
        "payers": [{"member_id": owner_id, "amount": "135.00"}],
        "components": [
            {"label": "Eligible groceries", "kind": "item", "amount": "100.00", "strategy": "equal", "shares": [{"member_id": owner_id}]},
            {"label": "Gift card", "kind": "item", "non_discountable": True, "amount": "50.00", "strategy": "equal", "shares": [{"member_id": owner_id}]},
            {"label": "20% eligible coupon", "kind": "discount", "promotion_id": "coupon-20", "discount_mode": "percentage", "percentage": "20", "cap": "15.00", "minimum_order": "80.00", "amount": "0.00", "eligible_component_indexes": [0], "strategy": "equal", "shares": [{"member_id": owner_id}]},
        ],
    }
    response = client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=base)
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["components"][2]["amount"]) == Decimal("-15.00")
    invalid = {**base, "idempotency_key": "11000000-0000-4000-8000-000000000003", "components": [*base["components"][:2], {**base["components"][2], "eligible_component_indexes": [1]}]}
    blocked = client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=invalid)
    assert blocked.status_code == 422
    cashback = {**base, "components": [*base["components"][:2], {**base["components"][2], "discount_mode": "cashback"}]}
    blocked = client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=cashback)
    assert blocked.status_code == 422
    assert "cashback" in blocked.json()["detail"].lower()
    stacked = {
        **base,
        "total": "130.00",
        "payers": [{"member_id": owner_id, "amount": "130.00"}],
        "components": [
            *base["components"],
            {"label": "Whole eligible bill voucher", "kind": "discount", "promotion_id": "bill-5", "discount_mode": "fixed", "amount": "-5.00", "strategy": "equal", "shares": [{"member_id": owner_id}]},
        ],
    }
    stacked_response = client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=stacked)
    assert stacked_response.status_code == 200, stacked_response.text
    assert Decimal(stacked_response.json()["components"][3]["basis"]) == Decimal("85.00")
    duplicate = {**stacked, "components": [*stacked["components"][:3], {**stacked["components"][3], "promotion_id": "coupon-20"}]}
    assert client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=duplicate).status_code == 422
    excessive = {**base, "total": "1.00", "payers": [{"member_id": owner_id, "amount": "1.00"}], "components": [*base["components"][:2], {**base["components"][2], "discount_mode": "fixed", "amount": "-200.00"}]}
    assert client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=excessive).status_code == 422


@pytest.mark.parametrize("mutator", [
    lambda body: body["payers"].__setitem__(0, {**body["payers"][0], "amount": "69.99"}),
    lambda body: body["components"].__setitem__(0, {**body["components"][0], "amount": "109.99"}),
])
def test_rejects_non_reconciling_inputs(client, mutator):
    group = create_group(client); owner_id = group["members"][0]["id"]
    body = {"idempotency_key": "20000000-0000-4000-8000-000000000001", "description": "Taxi", "total": "10.00", "currency": "GBP", "expense_date": "2026-10-18", "payers": [{"member_id": owner_id, "amount": "10.00"}], "components": [{"label": "Fare", "amount": "10.00", "strategy": "percentage", "shares": [{"member_id": owner_id, "value": "100"}]}]}
    mutator(body)
    response = client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=body)
    assert response.status_code == 422


def test_non_owner_registered_member_cannot_invite(client, db):
    group = create_group(client)
    client.get("/v1/preferences", headers=headers(USER_B))
    from expense_intelligence.models import GroupMember, User
    user_b = db.query(User).filter(User.auth_subject == f"dev:{USER_B}").one()
    member = client.post(f"/v1/groups/{group['id']}/members", headers=headers(), json={"display_name": "B", "linked_user_id": str(user_b.id)})
    assert member.status_code == 503
    linked = GroupMember(group_id=uuid.UUID(group["id"]), linked_user_id=user_b.id, display_name="B")
    db.add(linked); db.commit()
    denied = client.post(f"/v1/groups/{group['id']}/members", headers=headers(USER_B), json={"display_name": "Guest"})
    assert denied.status_code == 403


def test_owner_can_rename_archive_and_restore_without_deleting_history(client):
    group = create_group(client)
    renamed = client.put(f"/v1/groups/{group['id']}", headers=headers(), json={"expected_version": 1, "name": "London flat"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "London flat"
    archived = client.put(f"/v1/groups/{group['id']}", headers=headers(), json={"expected_version": 2, "archived": True})
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert client.get("/v1/groups", headers=headers()).json() == []
    assert client.get("/v1/groups?include_archived=true", headers=headers()).json()[0]["name"] == "London flat"
    restored = client.put(f"/v1/groups/{group['id']}", headers=headers(), json={"expected_version": 3, "archived": False})
    assert restored.status_code == 200
    assert restored.json()["archived"] is False
    stale = client.put(f"/v1/groups/{group['id']}", headers=headers(), json={"expected_version": 1, "name": "Stale"})
    assert stale.status_code == 409


def test_five_person_receipt_split_links_payment_and_attributes_consumption(client, db):
    user_ids = [f"00000000-0000-4000-8000-00000000000{index}" for index in range(1, 6)]
    for user_id in user_ids:
        assert client.get("/v1/preferences", headers=headers(user_id)).status_code == 200
    group = create_group(client)
    members = [group["members"][0]]
    for index, user_id in enumerate(user_ids[1:], start=1):
        user = db.query(User).filter_by(auth_subject=f"dev:{user_id}").one()
        member = GroupMember(group_id=uuid.UUID(group["id"]), linked_user_id=user.id, display_name=chr(65 + index))
        db.add(member); db.flush(); members.append({"id": str(member.id), "display_name": chr(65 + index)})
    owner = db.query(User).filter_by(auth_subject=f"dev:{USER_A}").one()
    payment = Transaction(owner_user_id=owner.id, description="Spice Route card payment", category="Dining", transaction_type=TransactionType.purchase, direction=TransactionDirection.expense, original_amount=Decimal("2600.00"), original_currency="INR", effective_date=date(2026, 10, 18), needs_review=False)
    db.add(payment); db.commit()
    categories = client.get("/v1/categories", headers=headers()).json()
    dining = next(row for row in categories if row["name"] == "Restaurants")
    alcohol = next(row for row in categories if row["name"] == "Alcohol")
    receipt = client.post("/v1/receipts", headers=headers(), json={
        "idempotency_key": "30000000-0000-4000-8000-000000000001", "source_hash": "a" * 64, "file_name": "synthetic-five-friends.png", "source_format": "png", "document_type": "receipt", "page_count": 1, "used_ocr": True, "elapsed_ms": 250,
        "candidate": {"merchant": "Spice Route", "document_date": "2026-10-18", "currency": "INR", "confidence": 0.91, "issues": [], "items": [
            {"label": "Chicken Tikka", "quantity": "1", "unit_price": "600", "line_total": "600", "category_id": dining["id"]},
            {"label": "Paneer Tikka", "quantity": "1", "unit_price": "450", "line_total": "450", "category_id": dining["id"]},
            {"label": "Beer", "quantity": "3", "unit_price": "300", "line_total": "900", "category_id": alcohol["id"]},
            {"label": "Naan", "quantity": "5", "unit_price": "50", "line_total": "250", "category_id": dining["id"]}],
            "discount": "-200", "tax": "360", "service_charge": "240", "tip": "0", "rounding": "0", "total": "2600"}})
    assert receipt.status_code == 201, receipt.text
    confirmed_receipt = client.post(f"/v1/receipts/{receipt.json()['id']}/confirm", headers=headers(), json={"expected_version": 1, "linked_transaction_id": str(payment.id)})
    assert confirmed_receipt.status_code == 200, confirmed_receipt.text
    ids = [row["id"] for row in members]
    def shares(indexes, values=None):
        return [{"member_id": ids[index], **({"value": values[position]} if values else {})} for position, index in enumerate(indexes)]
    payload = {"idempotency_key": "30000000-0000-4000-8000-000000000002", "description": "Spice Route", "total": "2600", "currency": "INR", "expense_date": "2026-10-18", "category_id": dining["id"], "source_receipt_id": receipt.json()["id"], "payers": [{"member_id": ids[0], "amount": "1600"}, {"member_id": ids[3], "amount": "1000"}], "components": [
        {"label": "Chicken Tikka", "amount": "600", "strategy": "equal", "category_id": dining["id"], "shares": shares([0, 3])},
        {"label": "Paneer Tikka", "amount": "450", "strategy": "equal", "category_id": dining["id"], "shares": shares([1, 2, 4])},
        {"label": "Beer", "amount": "900", "strategy": "equal", "category_id": alcohol["id"], "shares": shares([2, 3, 4])},
        {"label": "Naan", "amount": "250", "strategy": "equal", "category_id": dining["id"], "shares": shares([0, 1, 2, 3, 4])},
        {"label": "Bill discount", "amount": "-200", "strategy": "weighted", "shares": shares([0, 1, 2, 3, 4], ["350", "200", "500", "650", "500"])},
        {"label": "Food and alcohol tax", "amount": "360", "strategy": "weighted", "shares": shares([0, 2, 3, 4], ["350", "500", "650", "500"])},
        {"label": "Service charge", "amount": "240", "strategy": "equal", "shares": shares([0, 1, 2, 3, 4])}]}
    result = client.post(f"/v1/groups/{group['id']}/expenses", headers=headers(), json=payload)
    assert result.status_code == 201, result.text
    owed = {row["member_id"]: Decimal(row["owed"]) for row in result.json()["balances"]}
    assert [owed[ids[index]] for index in (0, 1, 3)] == [Decimal("429.18"), Decimal("229.82"), Decimal("755.91")]
    assert sorted([owed[ids[2]], owed[ids[4]]]) == [Decimal("592.54"), Decimal("592.55")]
    expense = db.query(SharedExpense).filter_by(id=uuid.UUID(result.json()["id"])).one()
    assert expense.linked_transaction_id == payment.id
    assert expense.source_receipt_id == uuid.UUID(receipt.json()["id"])
    assert db.query(ExpenseComponent).filter_by(expense_id=expense.id, category_id=uuid.UUID(alcohol["id"])).count() == 1
    analytics = client.get("/v1/analytics/overview?start=2026-10-01&end=2026-10-31", headers=headers()).json()
    assert analytics["totals"] == [{"currency": "INR", "spend": "429.18", "income": "0.00", "refunds": "0.00", "cash_outflow": "2600.00", "cash_income": "0.00", "net": "-429.18", "cash_net": "-2600.00", "unclassified": "0.00", "shared_consumption": "429.18"}]
    member_analytics = client.get("/v1/analytics/overview?start=2026-10-01&end=2026-10-31", headers=headers(user_ids[1])).json()
    assert member_analytics["totals"][0]["spend"] == "229.82"
    assert member_analytics["totals"][0]["shared_consumption"] == "229.82"
    budget = client.post("/v1/budgets", headers=headers(), json={"name": "Dining budget", "category_id": None, "amount": "1000", "currency": "INR", "period_type": "monthly", "start_date": "2026-10-01", "end_date": "2026-10-31", "time_zone": "Asia/Kolkata", "warning_percent": "80"})
    assert budget.status_code == 201, budget.text
    evaluation = client.get(f"/v1/budgets/{budget.json()['id']}", headers=headers()).json()
    assert Decimal(evaluation["spent"]) == Decimal("429.18")
    assert {row["description"] for row in evaluation["contributions"]} == {"Shared: Spice Route"}
    assert sum(Decimal(row["original_amount"]) for row in evaluation["contributions"]) == Decimal("429.18")


def test_archived_group_rejects_confirmation_but_keeps_preview(client):
    group = create_group(client); owner_id = group["members"][0]["id"]
    body = {"idempotency_key": "40000000-0000-4000-8000-000000000001", "description": "Historical plan", "total": "10.00", "currency": "INR", "expense_date": "2026-10-18", "payers": [{"member_id": owner_id, "amount": "10.00"}], "components": [{"label": "Meal", "amount": "10.00", "strategy": "equal", "shares": [{"member_id": owner_id}]}]}
    assert client.put(f"/v1/groups/{group['id']}", headers=headers(), json={"expected_version": 1, "archived": True}).status_code == 200
    assert client.post(f"/v1/groups/{group['id']}/expenses/preview", headers=headers(), json=body).status_code == 200
    blocked = client.post(f"/v1/groups/{group['id']}/expenses", headers=headers(), json=body)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Archived groups cannot accept new expenses"
