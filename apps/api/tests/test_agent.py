from decimal import Decimal

from expense_intelligence.agent.runtime import AgentResult
from expense_intelligence.agent.tools import aggregate_spending, compare_spending_periods, convert_currency, get_category_breakdown
from expense_intelligence.agent.private_tools import build_private_finance_tools
from expense_intelligence.config import Settings
from expense_intelligence.flags import FlagName, seed_flags
from expense_intelligence.models import FeatureFlag, Transaction, TransactionDirection, TransactionType, User
from datetime import date


HEADERS = {"X-Dev-User-Id": "00000000-0000-4000-8000-000000000123"}


def test_synthetic_tools_are_exact_and_labelled():
    october = aggregate_spending.invoke({"start": "2026-10-01", "end": "2026-10-31"})
    assert october == {"total": "6296.15", "currency": "INR", "count": 3, "data_mode": "synthetic_demo"}
    comparison = compare_spending_periods.invoke({"first_start": "2026-09-01", "first_end": "2026-09-30", "second_start": "2026-10-01", "second_end": "2026-10-31"})
    assert comparison["difference"] == "1425.65"
    assert get_category_breakdown.invoke({"start": "2026-10-01", "end": "2026-10-31"})["categories"]["Groceries"] == "3160.75"
    assert convert_currency.invoke({"amount": Decimal("1000"), "base": "INR", "quote": "GBP"})["result"] == "8.55"


def test_chat_history_flag_is_independent(client, db, monkeypatch):
    seed_flags(db)
    monkeypatch.setattr("expense_intelligence.chat.run_agent", lambda *args: AgentResult("Synthetic answer", ["aggregate_spending"]))

    ephemeral = client.post("/v1/agent/chat", headers=HEADERS, json={"content": "October total?"})
    assert ephemeral.status_code == 200
    assert client.get("/v1/chat/threads", headers=HEADERS).json() == []

    db.get(FeatureFlag, FlagName.CHAT_HISTORY.value).enabled = True
    db.commit()
    persisted = client.post("/v1/agent/chat", headers=HEADERS, json={"content": "October total?"})
    assert persisted.status_code == 200
    thread_id = persisted.json()["thread_id"]
    assert len(client.get("/v1/chat/threads", headers=HEADERS).json()) == 1
    messages = client.get(f"/v1/chat/threads/{thread_id}/messages", headers=HEADERS).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]


def test_agent_disabled_without_network_call(client):
    response = client.post("/v1/agent/chat", headers=HEADERS, json={"content": "Hello"})
    assert response.status_code == 503
    assert response.json()["detail"] == "The finance agent is disabled"


def test_private_tool_registry_is_read_only_and_owner_scoped(client, db):
    other_headers = {"X-Dev-User-Id": "00000000-0000-4000-8000-000000000124"}
    client.get("/v1/preferences", headers=HEADERS)
    client.get("/v1/preferences", headers=other_headers)
    owner = db.query(User).filter_by(auth_subject="dev:00000000-0000-4000-8000-000000000123").one()
    other = db.query(User).filter_by(auth_subject="dev:00000000-0000-4000-8000-000000000124").one()
    db.add_all([
        Transaction(owner_user_id=owner.id, description="Owner groceries", category="Groceries", direction=TransactionDirection.expense, transaction_type=TransactionType.purchase, original_amount=Decimal("42.50"), original_currency="GBP", effective_date=date(2026, 10, 1)),
        Transaction(owner_user_id=other.id, description="Other private salary", category="Income", direction=TransactionDirection.income, transaction_type=TransactionType.income, original_amount=Decimal("9000"), original_currency="GBP", effective_date=date(2026, 10, 1)),
    ])
    db.commit()
    tools = {tool.name: tool for tool in build_private_finance_tools(db, owner.id)}
    assert set(tools) == {"search_real_transactions", "real_category_spending", "list_real_merchants", "real_budget_progress", "real_finance_insights", "real_group_balances", "real_settlement_history", "real_import_history", "cached_real_currency_conversion"}
    result = tools["search_real_transactions"].invoke({"query": "", "limit": 20})
    assert [row["description"] for row in result["transactions"]] == ["Owner groceries"]
    assert all("create" not in name and "update" not in name and "delete" not in name and "record" not in name for name in tools)


def test_configuration_can_load_key_without_exposing_it(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=test-secret-never-log\nAGENT_MODE=disabled\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.gemini_api_key is not None
    assert settings.agent_mode == "disabled"
    assert "test-secret-never-log" not in repr(settings)


def test_all_provider_keys_are_redacted(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=g-secret\nGROQ_API_KEY=q-secret\nOPENROUTER_API_KEY=o-secret\nMISTRAL_API_KEY=m-secret\n", encoding="utf-8")
    rendered = repr(Settings(_env_file=env_file))
    assert all(secret not in rendered for secret in ("g-secret", "q-secret", "o-secret", "m-secret"))


def test_prompt_injection_cannot_enable_real_tools():
    from expense_intelligence.agent.runtime import SYSTEM_PROMPT
    from expense_intelligence.agent.tools import FINANCE_TOOLS
    assert "synthetic" in SYSTEM_PROMPT.lower()
    assert all("real" not in tool.name for tool in FINANCE_TOOLS)


def test_multi_tool_followup_wiring_without_live_model(monkeypatch):
    from langchain_core.messages import AIMessage
    from expense_intelligence.agent.runtime import run_agent
    captured = {}

    class FakeGraph:
        def invoke(self, payload):
            captured["messages"] = payload["messages"]
            return {"messages": payload["messages"] + [AIMessage(content="Grounded synthetic comparison")], "trace": [{"tool":"aggregate_spending"},{"tool":"get_category_breakdown"}]}

    monkeypatch.setattr("expense_intelligence.agent.runtime.build_model", lambda settings: object())
    monkeypatch.setattr("expense_intelligence.agent.runtime.build_agent_graph", lambda *args, **kwargs: FakeGraph())
    result = run_agent(Settings(agent_mode="synthetic_developer", gemini_api_key="synthetic-test-key"), "Why?", [("user", "Compare October"), ("assistant", "October increased")], "Preferred currency: INR")
    assert result.tools_used == ["aggregate_spending", "get_category_breakdown"]
    assert [message.type for message in captured["messages"]] == ["system", "system", "human", "ai", "human"]


def test_model_failure_is_redacted(monkeypatch):
    from expense_intelligence.agent.runtime import run_agent

    class FailedGraph:
        def invoke(self, *args, **kwargs):
            raise TimeoutError("provider detail with request internals")

    monkeypatch.setattr("expense_intelligence.agent.runtime.build_model", lambda settings: object())
    monkeypatch.setattr("expense_intelligence.agent.runtime.build_agent_graph", lambda *args, **kwargs: FailedGraph())
    try:
        run_agent(Settings(agent_mode="synthetic_developer", gemini_api_key="synthetic-test-key"), "Hello", [])
        assert False, "Expected a redacted runtime failure"
    except RuntimeError as exc:
        assert str(exc) == "The finance assistant is temporarily unavailable"
