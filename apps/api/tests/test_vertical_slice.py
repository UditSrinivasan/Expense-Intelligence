from datetime import date
from decimal import Decimal

from sqlalchemy import select

from expense_intelligence.flags import FlagName, is_enabled, seed_flags
from expense_intelligence.models import AuditEvent, FxRate, Transaction


USER_A = "00000000-0000-4000-8000-000000000001"
USER_B = "00000000-0000-4000-8000-000000000002"


def auth(user_id: str) -> dict[str, str]:
    return {"X-Dev-User-Id": user_id}


def test_authentication_required(client):
    assert client.get("/v1/transactions").status_code == 401


def test_repeated_identity_provisioning_is_idempotent(client):
    assert client.get("/v1/transactions", headers=auth(USER_A)).status_code == 200
    assert client.get("/v1/transactions", headers=auth(USER_A)).status_code == 200


def test_preferences_and_transaction_are_user_scoped(client, db):
    preference = {
        "country_code": "GB",
        "locale": "en-GB",
        "home_currency": "GBP",
        "display_currency": "GBP",
        "time_zone": "Europe/London",
    }
    assert client.put("/v1/preferences", headers=auth(USER_A), json=preference).json() == preference

    payload = {
        "description": "Groceries",
        "category": "Groceries",
        "direction": "expense",
        "original_amount": "12.35",
        "original_currency": "GBP",
        "effective_date": "2026-10-17",
    }
    created = client.post("/v1/transactions", headers=auth(USER_A), json=payload)
    assert created.status_code == 201
    assert client.get("/v1/transactions", headers=auth(USER_A)).json()[0]["original_amount"] == "12.350000000000"
    assert client.get("/v1/transactions", headers=auth(USER_B)).json() == []
    assert len(client.get("/v1/transactions?query=grocer&currency=GBP&start=2026-10-01&end=2026-10-31", headers=auth(USER_A)).json()) == 1
    assert client.get("/v1/transactions?transaction_type=income", headers=auth(USER_A)).json() == []
    assert client.get("/v1/transactions?start=2026-11-01&end=2026-10-01", headers=auth(USER_A)).status_code == 422

    summary = client.get("/v1/dashboard?currency=GBP", headers=auth(USER_A)).json()
    assert Decimal(summary["expenses"]) == Decimal("12.35")
    assert Decimal(summary["net"]) == Decimal("-12.35")
    assert client.get("/v1/dashboard?currency=GBP", headers=auth(USER_B)).json()["transaction_count"] == 0

    assert db.scalar(select(Transaction)) is not None
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "transaction.created")) is not None


def test_manual_transaction_account_must_belong_to_user(client):
    account = client.post("/v1/accounts", headers=auth(USER_A), json={"name": "Daily", "currency": "INR"}).json()
    payload = {"description": "Manual purchase", "direction": "expense", "original_amount": "10.25", "original_currency": "INR", "effective_date": "2026-10-24", "account_id": account["id"]}
    created = client.post("/v1/transactions", headers=auth(USER_A), json=payload)
    assert created.status_code == 201 and created.json()["account_id"] == account["id"]
    assert client.post("/v1/transactions", headers=auth(USER_B), json=payload).status_code == 404


def test_profiles_are_private_and_onboarding_is_explicit(client):
    profile = {"display_name": "Asha", "country_code": "IN", "locale": "en-IN", "home_currency": "INR", "display_currency": "INR", "time_zone": "Asia/Kolkata"}
    saved = client.put("/v1/profile", headers=auth(USER_A), json=profile)
    assert saved.status_code == 200 and saved.json()["onboarding_completed"] is True
    other = client.get("/v1/profile", headers=auth(USER_B)).json()
    assert other["display_name"] == "" and other["onboarding_completed"] is False


def test_fx_uses_cached_provenance_and_decimal_rounding(client, db):
    db.add(
        FxRate(
            provider="frankfurter",
            base_currency="GBP",
            quote_currency="INR",
            rate=Decimal("110.125"),
            rate_date=date(2026, 10, 16),
            attribution="test fixture",
        )
    )
    db.commit()
    response = client.get("/v1/fx/convert?amount=2.50&base=GBP&quote=INR", headers=auth(USER_A))
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["result"]) == Decimal("275.31")
    assert body["provider"] == "Frankfurter"
    assert body["rate_type"] == "latest_available_daily_reference"


def test_memory_flags_are_independent_and_disabled_by_default(db):
    seed_flags(db)
    assert all(not is_enabled(db, flag) for flag in FlagName)
