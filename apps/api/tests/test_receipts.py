import uuid
from datetime import date
from decimal import Decimal

from expense_intelligence.models import ReceiptDocument, Transaction, TransactionAllocation, User
from test_ingestion import account
from test_splitting import USER_A, USER_B, headers


def candidate(categories, currency="GBP"):
    return {
        "merchant": "Green Market",
        "document_date": "2026-10-18",
        "currency": currency,
        "items": [
            {"label": "Groceries", "quantity": "1", "unit_price": "25.00", "line_total": "25.00", "category_id": categories[0]},
            {"label": "Wine", "quantity": "1", "unit_price": "12.00", "line_total": "12.00", "category_id": categories[1]},
            {"label": "Household", "quantity": "1", "unit_price": "8.00", "line_total": "8.00", "category_id": categories[0]},
        ],
        "discount": "0.00", "tax": "0.00", "service_charge": "0.00", "tip": "0.00", "rounding": "0.00",
        "total": "45.00", "confidence": 0.81, "issues": [],
    }


def stage(client, account_id, receipt, key="71000000-0000-4000-8000-000000000001"):
    return client.post("/v1/receipts", headers=headers(), json={"idempotency_key": key, "account_id": account_id, "source_hash": "c" * 64, "file_name": "synthetic-uk-receipt.png", "source_format": "png", "document_type": "receipt", "page_count": 1, "used_ocr": True, "elapsed_ms": 1240, "candidate": receipt})


def test_receipt_reconciliation_matching_link_and_allocation(client, db):
    acc = account(client, "GBP")
    category_rows = [row for row in client.get("/v1/categories", headers=headers()).json() if row["parent_id"]][:2]
    owner = db.query(User).filter(User.auth_subject == f"dev:{USER_A}").one()
    transaction = Transaction(owner_user_id=owner.id, account_id=uuid.UUID(acc["id"]), description="GREEN MARKET CARD", raw_description="GREEN MARKET CARD", normalized_description="green market card", category="Other", direction="expense", transaction_type="purchase", classification_source="unclassified", needs_review=True, original_amount=Decimal("45.00"), original_currency="GBP", effective_date=date(2026, 10, 18))
    db.add(transaction); db.commit()
    response = stage(client, acc["id"], candidate([row["id"] for row in category_rows]))
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["matches"][0]["transaction_id"] == str(transaction.id)
    confirmed = client.post(f"/v1/receipts/{receipt['id']}/confirm", headers=headers(), json={"expected_version": 1, "linked_transaction_id": str(transaction.id)})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["linked_transaction_id"] == str(transaction.id)
    assert db.query(Transaction).count() == 1
    allocations = db.query(TransactionAllocation).filter_by(transaction_id=transaction.id, current=True).all()
    assert sum((row.amount for row in allocations), Decimal(0)) == Decimal("45")
    retry = client.post(f"/v1/receipts/{receipt['id']}/confirm", headers=headers(), json={"expected_version": 1, "linked_transaction_id": str(transaction.id)})
    assert retry.status_code == 200 and db.query(TransactionAllocation).filter_by(transaction_id=transaction.id).count() == 2


def test_receipt_rejects_bad_reconciliation_and_cross_user_access(client, db):
    acc = account(client, "GBP")
    categories = [row["id"] for row in client.get("/v1/categories", headers=headers()).json() if row["parent_id"]][:2]
    broken = candidate(categories); broken["total"] = "46.00"
    assert stage(client, acc["id"], broken).status_code == 422
    receipt = stage(client, acc["id"], candidate(categories), "71000000-0000-4000-8000-000000000002").json()
    assert client.get(f"/v1/receipts/{receipt['id']}", headers=headers(USER_B)).status_code == 404
    assert client.post(f"/v1/receipts/{receipt['id']}/confirm", headers=headers(USER_B), json={"expected_version": 1}).status_code == 404
    assert db.query(ReceiptDocument).count() == 1


def test_receipt_match_is_conservative_on_date_currency_and_amount(client, db):
    acc = account(client, "INR")
    categories = [row["id"] for row in client.get("/v1/categories", headers=headers()).json() if row["parent_id"]][:2]
    receipt = candidate(categories, "INR")
    response = stage(client, acc["id"], receipt, "71000000-0000-4000-8000-000000000003")
    assert response.status_code == 201 and response.json()["matches"] == []
