"""PostgreSQL-only checks for locking, idempotency, and physical schema fidelity."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from expense_intelligence.models import ExpenseAllocation, Settlement, Transaction, User
from test_group_finance import settlement_body, setup_debt
from test_ingestion import account, candidate, stage
from test_splitting import headers


pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="requires the disposable PostgreSQL test database",
)


def _parallel_post(client, url, bodies):
    def send(body):
        return client.post(url, headers=headers(), json=body)

    with ThreadPoolExecutor(max_workers=len(bodies)) as executor:
        return list(executor.map(send, bodies))


def test_postgresql_schema_preserves_money_precision_constraints_and_indexes(db):
    inspector = inspect(db.get_bind())
    amount = next(column for column in inspector.get_columns("transactions") if column["name"] == "original_amount")
    assert (amount["type"].precision, amount["type"].scale) == (38, 12)
    assert "ix_transactions_owner_date" in {index["name"] for index in inspector.get_indexes("transactions")}
    assert "uq_import_batch_idempotency" in {
        constraint["name"] for constraint in inspector.get_unique_constraints("import_batches")
    }


def test_concurrent_settlements_serialize_and_conserve_group_balance(client, db):
    group, owner, guest, _, _ = setup_debt(client)
    url = f"/v1/groups/{group['id']}/settlements"
    responses = _parallel_post(
        client,
        url,
        [
            settlement_body(group, guest, owner, "10.00", "35000000-0000-4000-8000-000000000001"),
            settlement_body(group, guest, owner, "10.00", "35000000-0000-4000-8000-000000000002"),
        ],
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert db.query(Settlement).count() == 1
    balances = client.get(f"/v1/groups/{group['id']}/balances", headers=headers()).json()
    assert sum(Decimal(row["balance"]) for row in balances) == Decimal("0")
    assert sum(row.amount for row in db.query(ExpenseAllocation).all()) == Decimal("100.000000000000")


def test_concurrent_duplicate_import_confirmation_is_idempotent(client, db):
    financial_account = account(client)
    batch = stage(
        client,
        financial_account["id"],
        [candidate(2, "Synthetic grocery", "expense", "19.99")],
        "65000000-0000-4000-8000-000000000001",
    )
    url = f"/v1/imports/{batch['id']}/confirm"
    responses = _parallel_post(client, url, [{"expected_version": batch["version"]}] * 2)
    assert [response.status_code for response in responses] == [200, 200]
    assert db.query(Transaction).filter(Transaction.import_batch_id == batch["id"]).count() == 1


def test_transaction_rollback_does_not_persist_partial_financial_rows(db):
    subject = f"rollback:{uuid.uuid4()}"
    try:
        db.add(User(auth_subject=subject))
        db.flush()
        raise RuntimeError("force transaction rollback")
    except RuntimeError:
        db.rollback()
    assert db.query(User).filter_by(auth_subject=subject).one_or_none() is None
