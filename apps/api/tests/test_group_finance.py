from decimal import Decimal
import uuid

from expense_intelligence.models import SharedExpense

from test_splitting import USER_A, USER_B, create_group, headers


def setup_debt(client, currency="INR", key="31000000-0000-4000-8000-000000000001"):
    group = create_group(client); owner = group["members"][0]
    guest = client.post(f"/v1/groups/{group['id']}/members", headers=headers(), json={"display_name": "Ben"}).json()
    payload = {"idempotency_key": key, "description": "Shared bill", "total": "100.00", "currency": currency, "expense_date": "2026-10-18", "payers": [{"member_id": owner["id"], "amount": "100.00"}], "components": [{"label": "Bill", "amount": "100.00", "strategy": "equal", "shares": [{"member_id": owner["id"]}, {"member_id": guest["id"]}]}]}
    expense = client.post(f"/v1/groups/{group['id']}/expenses", headers=headers(), json=payload)
    assert expense.status_code == 201, expense.text
    return group, owner, guest, payload, expense.json()


def settlement_body(group, guest, owner, amount, key, expected=3, status="confirmed"):
    return {"idempotency_key": key, "expected_group_version": expected, "payer_member_id": guest["id"], "payee_member_id": owner["id"], "amount": amount, "currency": "INR", "settlement_date": "2026-10-18", "reference": "UPI reference", "status": status}


def test_partial_full_duplicate_overpayment_and_reversal(client):
    group, owner, guest, _, _ = setup_debt(client)
    partial_body = settlement_body(group, guest, owner, "20.00", "32000000-0000-4000-8000-000000000001")
    partial = client.post(f"/v1/groups/{group['id']}/settlements", headers=headers(), json=partial_body)
    assert partial.status_code == 201, partial.text
    duplicate = client.post(f"/v1/groups/{group['id']}/settlements", headers=headers(), json=partial_body)
    assert duplicate.status_code == 201 and duplicate.json()["id"] == partial.json()["id"]
    balances = client.get(f"/v1/groups/{group['id']}/balances", headers=headers()).json()
    assert next(Decimal(row["balance"]) for row in balances if row["member_id"] == guest["id"]) == Decimal("-30")
    overpay = client.post(f"/v1/groups/{group['id']}/settlements", headers=headers(), json=settlement_body(group, guest, owner, "30.01", "32000000-0000-4000-8000-000000000002", 4))
    assert overpay.status_code == 422
    full = client.post(f"/v1/groups/{group['id']}/settlements", headers=headers(), json=settlement_body(group, guest, owner, "30.00", "32000000-0000-4000-8000-000000000003", 4))
    assert full.status_code == 201, full.text
    assert all(Decimal(row["balance"]) == 0 for row in client.get(f"/v1/groups/{group['id']}/balances", headers=headers()).json())
    reversal = client.post(f"/v1/groups/{group['id']}/settlements/{full.json()['id']}/reverse", headers=headers(), json={"idempotency_key": "32000000-0000-4000-8000-000000000004", "expected_group_version": 5, "reference": "Entered twice"})
    assert reversal.status_code == 201 and reversal.json()["kind"] == "reversal"
    assert next(Decimal(row["balance"]) for row in client.get(f"/v1/groups/{group['id']}/balances", headers=headers()).json() if row["member_id"] == guest["id"]) == Decimal("-30")


def test_pending_confirmation_stale_concurrency_and_authorization(client):
    group, owner, guest, _, _ = setup_debt(client)
    pending = client.post(f"/v1/groups/{group['id']}/settlements", headers=headers(), json=settlement_body(group, guest, owner, "10.00", "33000000-0000-4000-8000-000000000001", status="pending"))
    assert pending.status_code == 201
    assert next(Decimal(row["balance"]) for row in client.get(f"/v1/groups/{group['id']}/balances", headers=headers()).json() if row["member_id"] == guest["id"]) == Decimal("-50")
    assert client.post(f"/v1/groups/{group['id']}/settlements/{pending.json()['id']}/confirm?expected_group_version=1", headers=headers()).status_code == 409
    confirmed = client.post(f"/v1/groups/{group['id']}/settlements/{pending.json()['id']}/confirm?expected_group_version=4", headers=headers())
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"
    assert client.get(f"/v1/groups/{group['id']}/settlements", headers=headers(USER_B)).status_code == 404
    assert client.get(f"/v1/groups/{group['id']}/analytics", headers=headers(USER_B)).status_code == 404


def test_templates_update_apply_and_do_not_change_history(client, db):
    group, owner, guest, _, expense = setup_debt(client)
    template = {"name": "Monthly utilities", "description": "Electricity", "currency": "INR", "components": [{"label": "Usage", "amount": "100.00", "strategy": "usage", "shares": [{"member_id": owner["id"], "value": "40"}, {"member_id": guest["id"], "value": "60"}]}]}
    created = client.post(f"/v1/groups/{group['id']}/templates", headers=headers(), json=template)
    assert created.status_code == 201, created.text
    updated = client.put(f"/v1/groups/{group['id']}/templates/{created.json()['id']}", headers=headers(), json={**template, "name": "Utilities", "expected_version": 1})
    assert updated.status_code == 200 and updated.json()["version"] == 2
    draft = client.post(f"/v1/groups/{group['id']}/templates/{created.json()['id']}/apply", headers=headers()).json()
    assert draft["payers"] == [] and draft["template_version"] == 2 and draft["components"][0]["strategy"] == "usage"
    assert db.get(SharedExpense, uuid.UUID(expense["id"])).description == "Shared bill"


def test_expense_detail_is_authorized_exact_and_share_ready(client):
    group, owner, guest, _, expense = setup_debt(client, currency="KWD")
    response = client.get(f"/v1/groups/{group['id']}/expenses/{expense['id']}", headers=headers())
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["currency_quantum"] == "0.001"
    assert detail["reconciliation"] == {"payer_total": "100.000000000000", "component_total": "100.000000000000", "allocation_total": "100.000000000000", "reconciled": True}
    assert detail["participants"][0]["display_name"] in {owner["display_name"], guest["display_name"]}
    assert sum(Decimal(row["amount"]) for row in detail["obligations"]) == Decimal("50")
    assert client.get(f"/v1/groups/{group['id']}/expenses/{expense['id']}", headers=headers(USER_B)).status_code == 404


def test_correction_member_lifecycle_multicurrency_suggestions_and_analytics(client, db):
    group, owner, guest, original, expense = setup_debt(client)
    replacement = {**original, "idempotency_key": "34000000-0000-4000-8000-000000000001", "total": "60.00", "payers": [{"member_id": owner["id"], "amount": "60.00"}], "components": [{"label": "Corrected", "amount": "60.00", "strategy": "equal", "shares": [{"member_id": owner["id"]}, {"member_id": guest["id"]}]}]}
    proposal = client.post(f"/v1/groups/{group['id']}/expenses/{expense['id']}/correction-preview", headers=headers(), json={"expected_group_version": 3, "replacement": replacement})
    assert proposal.status_code == 200 and proposal.json()["blocked_by_confirmed_settlements"] is False
    corrected = client.post(f"/v1/groups/{group['id']}/expenses/{expense['id']}/correct", headers=headers(), json={"expected_group_version": 3, "replacement": replacement})
    assert corrected.status_code == 201, corrected.text
    assert db.get(SharedExpense, uuid.UUID(expense["id"])).state == "reversed"
    inactive = client.put(f"/v1/groups/{group['id']}/members/{guest['id']}", headers=headers(), json={"expected_group_version": 4, "active": False, "display_name": "Ben (left)"})
    assert inactive.status_code == 200 and Decimal(inactive.json()["outstanding_balances"][0]["balance"]) == Decimal("-30")
    balances = client.get(f"/v1/groups/{group['id']}/balances", headers=headers()).json()
    assert any(row["member_id"] == guest["id"] and row["active"] is False for row in balances)
    suggestions = client.get(f"/v1/groups/{group['id']}/debt-suggestions", headers=headers()).json()
    assert sum(Decimal(row["amount"]) for row in suggestions["suggestions"]) == Decimal("30")
    analytics = client.get(f"/v1/groups/{group['id']}/analytics", headers=headers()).json()
    assert Decimal(analytics["totals_by_currency"]["INR"]) == Decimal("60")
    assert len(analytics["recent_expenses"]) == 1
