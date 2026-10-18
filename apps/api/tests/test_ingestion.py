import json
import uuid
from decimal import Decimal

import pytest

from expense_intelligence.models import ImportBatch, ImportMappingProfile, ImportRow, Transaction
from test_splitting import USER_A, USER_B, headers


def account(client, currency="INR"):
    response = client.post("/v1/accounts", headers=headers(), json={"name": f"{currency} current", "currency": currency})
    assert response.status_code == 201
    return response.json()


def stage(client, account_id, candidates, key="61000000-0000-4000-8000-000000000001", name="statement.csv"):
    response = client.post("/v1/imports/stage", headers=headers(), json={"idempotency_key": key, "account_id": account_id, "source_hash": "a" * 64, "file_name": name, "file_format": "xlsx" if name.endswith(".xlsx") else "csv", "sheet_name": "Transactions", "mapping": {"Date": "transaction_date", "Narration": "description"}, "mapping_profile_name": "My bank", "candidates": candidates})
    assert response.status_code == 201, response.text
    return response.json()


def candidate(row, description, direction, amount, currency="INR", reference=None):
    return {"source_row": row, "transaction_date": "2026-10-18", "description": description, "direction": direction, "amount": amount, "currency": currency, "reference": reference, "included": True}


def test_india_uk_recognition_review_confirmation_history_and_idempotency(client, db):
    inr = account(client)
    batch = stage(client, inr["id"], [candidate(2, "UPI/merchant/123", "expense", "125.50", reference="UPI123"), candidate(3, "Salary credit", "income", "50000.00")])
    assert batch["rows"][0]["transaction_type"] == "transfer"
    assert batch["rows"][0]["review_state"] == "needs_review"
    assert batch["rows"][1]["transaction_type"] == "income"
    assert db.query(ImportMappingProfile).filter_by(name="My bank").one().version == 1
    reviewed = client.put(f"/v1/imports/{batch['id']}/rows/{batch['rows'][0]['id']}", headers=headers(), json={"expected_batch_version": batch["version"], "duplicate_action": "import"}).json()
    confirmed = client.post(f"/v1/imports/{batch['id']}/confirm", headers=headers(), json={"expected_version": reviewed["version"]})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    retry = client.post(f"/v1/imports/{batch['id']}/confirm", headers=headers(), json={"expected_version": 1})
    assert retry.status_code == 200
    transactions = db.query(Transaction).filter(Transaction.import_batch_id == uuid.UUID(batch["id"])).all()
    assert len(transactions) == 2 and transactions[0].original_amount == Decimal("125.500000000000")
    assert all(row.account_id == uuid.UUID(inr["id"]) for row in transactions)
    history = client.get("/v1/imports", headers=headers()).json()
    assert history[0]["status"] == "confirmed" and history[0]["row_count"] == 2
    assert client.get(f"/v1/imports/{batch['id']}", headers=headers(USER_B)).status_code == 404

    gbp = account(client, "GBP")
    uk = stage(client, gbp["id"], [candidate(2, "DIRECT DEBIT WATER", "expense", "31.27", "GBP"), candidate(3, "FASTER PAYMENT FROM EMPLOYER", "income", "900.00", "GBP")], "61000000-0000-4000-8000-000000000002", "uk.xlsx")
    assert uk["rows"][0]["transaction_type"] == "purchase"
    assert uk["rows"][1]["transaction_type"] == "transfer" and uk["rows"][1]["review_state"] == "needs_review"


def test_exact_and_likely_duplicates_are_never_silently_removed(client, db):
    acc = account(client)
    existing = Transaction(owner_user_id=db.query(ImportBatch).first().owner_user_id if db.query(ImportBatch).first() else None, account_id=uuid.UUID(acc["id"]), description="Coffee Shop", raw_description="Coffee Shop", normalized_description="coffee shop", category="Other", direction="expense", transaction_type="purchase", classification_source="unclassified", needs_review=True, original_amount=Decimal("250.00"), original_currency="INR", effective_date=__import__("datetime").date(2026, 10, 18), source_reference="REF-1")
    # Resolve the provisioned owner without coupling the test to authentication internals.
    from expense_intelligence.models import User
    existing.owner_user_id = db.query(User).filter(User.auth_subject == f"dev:{USER_A}").one().id
    db.add(existing); db.commit()
    batch = stage(client, acc["id"], [candidate(2, "Coffee Shop", "expense", "250.00", reference="REF-1"), {**candidate(3, "Coffee Shop", "expense", "250.00"), "transaction_date": "2026-10-20"}], "62000000-0000-4000-8000-000000000001")
    assert [row["duplicate_kind"] for row in batch["rows"]] == ["exact", "likely"]
    assert all(row["review_state"] == "needs_review" for row in batch["rows"])
    assert db.query(ImportRow).filter(ImportRow.batch_id == uuid.UUID(batch["id"])).count() == 2


def test_stale_review_and_atomic_rollback(client, db):
    acc = account(client)
    batch = stage(client, acc["id"], [candidate(2, "Card purchase", "expense", "10.00")], "63000000-0000-4000-8000-000000000001")
    row_id = batch["rows"][0]["id"]
    first = client.put(f"/v1/imports/{batch['id']}/rows/{row_id}", headers=headers(), json={"expected_batch_version": 1, "description": "Corrected card purchase"})
    assert first.status_code == 200
    stale = client.put(f"/v1/imports/{batch['id']}/rows/{row_id}", headers=headers(), json={"expected_batch_version": 1, "description": "Concurrent edit"})
    assert stale.status_code == 409
    row = db.get(ImportRow, uuid.UUID(row_id)); values = json.loads(row.candidate_json); values["transaction_type"] = "not-a-real-type"; row.candidate_json = json.dumps(values); db.commit()
    before = db.query(Transaction).count()
    with pytest.raises(ValueError):
        client.post(f"/v1/imports/{batch['id']}/confirm", headers=headers(), json={"expected_version": 2})
    assert db.query(Transaction).count() == before
    assert db.get(ImportBatch, uuid.UUID(batch["id"])).status == "review"


def test_rejects_bad_hash_foreign_account_and_row_limit_contract(client):
    acc = account(client)
    invalid = client.post("/v1/imports/stage", headers=headers(), json={"idempotency_key": str(uuid.uuid4()), "account_id": acc["id"], "source_hash": "bad", "file_name": "bad.exe", "file_format": "csv", "candidates": [candidate(2, "x", "expense", "1")]})
    assert invalid.status_code == 422
    foreign = client.post("/v1/imports/stage", headers=headers(USER_B), json={"idempotency_key": str(uuid.uuid4()), "account_id": acc["id"], "source_hash": "b" * 64, "file_name": "x.csv", "file_format": "csv", "candidates": [candidate(2, "x", "expense", "1")]})
    assert foreign.status_code == 404
