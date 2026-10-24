"""Execute RLS as a non-owner role; policy creation alone is not authorization proof."""

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from expense_intelligence.models import GroupMember, GroupRole, User
from test_splitting import headers


pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"), reason="requires disposable PostgreSQL")
USER_A = "00000000-0000-4000-8000-000000000001"
USER_B = "00000000-0000-4000-8000-000000000002"


def test_non_owner_rls_and_transaction_context_reset(client, db: Session):
    transaction = {"description":"Private synthetic record", "category":"Other", "direction":"expense", "original_amount":"10.00", "original_currency":"INR", "effective_date":"2026-10-24"}
    assert client.post("/v1/transactions", headers=headers(USER_A), json=transaction).status_code == 201
    assert client.post("/v1/transactions", headers=headers(USER_B), json={**transaction, "description":"Other private record"}).status_code == 201
    group = client.post("/v1/groups", headers=headers(USER_A), json={"name":"Synthetic shared group", "default_currency":"INR", "owner_name":"A"}).json()
    client.post("/v1/groups", headers=headers(USER_B), json={"name":"Private B group", "default_currency":"GBP", "owner_name":"B"})
    user_a = db.scalar(select(User).where(User.auth_subject == f"dev:{USER_A}")); user_b = db.scalar(select(User).where(User.auth_subject == f"dev:{USER_B}"))
    db.add(GroupMember(group_id=uuid.UUID(group["id"]), linked_user_id=user_b.id, display_name="B", role=GroupRole.member)); db.commit()

    sql = (Path(__file__).parents[3] / "supabase" / "rls.sql").read_text(encoding="utf-8")
    raw = db.get_bind().raw_connection()
    try:
        raw.cursor().execute(sql); raw.commit()
    finally:
        raw.close()

    role = f"expense_rls_{uuid.uuid4().hex[:10]}"
    engine = db.get_bind()
    with engine.begin() as connection:
        connection.exec_driver_sql(f'create role "{role}" noinherit nosuperuser nocreatedb nocreaterole nobypassrls')
        connection.exec_driver_sql(f'grant usage on schema public, app_private to "{role}"')
        connection.exec_driver_sql(f'grant select, insert, update, delete on all tables in schema public to "{role}"')
        connection.exec_driver_sql(f'grant execute on all functions in schema app_private to "{role}"')
        flags = connection.execute(text("select rolsuper, rolbypassrls from pg_roles where rolname=:role"), {"role":role}).one()
        assert flags == (False, False)
        assert connection.execute(text("select count(*) from pg_class where relowner=(select oid from pg_roles where rolname=:role)"), {"role":role}).scalar_one() == 0
    try:
        with engine.connect() as connection:
            transaction_scope = connection.begin()
            connection.exec_driver_sql(f'set local role "{role}"')
            connection.execute(text("select set_config('app.auth_subject', :value, true)"), {"value":f"dev:{USER_A}"})
            connection.execute(text("select set_config('app.current_user_id', :value, true)"), {"value":str(user_a.id)})
            assert connection.execute(text("select description from transactions")).scalars().all() == ["Private synthetic record"]
            assert connection.execute(text("select name from expense_groups")).scalars().all() == ["Synthetic shared group"]
            transaction_scope.rollback()
        with engine.connect() as connection:
            transaction_scope = connection.begin()
            connection.exec_driver_sql(f'set local role "{role}"')
            assert connection.execute(text("select count(*) from transactions")).scalar_one() == 0
            transaction_scope.rollback()

        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as scoped:
            scoped.info.update(auth_subject=f"dev:{USER_A}", current_user_id=str(user_a.id), current_user_email=f"dev+{USER_A}@example.invalid")
            assert scoped.scalar(text("select current_setting('app.current_user_id', true)")) == str(user_a.id)
            scoped.commit()
            assert scoped.scalar(text("select current_setting('app.current_user_id', true)")) == str(user_a.id)
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'drop owned by "{role}"')
            connection.exec_driver_sql(f'drop role "{role}"')
            connection.exec_driver_sql("drop policy if exists member_write on group_members")
            connection.exec_driver_sql("drop schema if exists app_private cascade")
