import asyncio
from time import perf_counter

import pytest

from expense_intelligence.agent.runtime import run_agent
from expense_intelligence.config import Settings


class StalledModel:
    def __init__(self): self.cancelled = False
    def bind_tools(self, tools): return self
    async def ainvoke(self, messages):
        try: await asyncio.Event().wait()
        except asyncio.CancelledError: self.cancelled = True; raise


def test_total_deadline_cancels_provider_task_and_redacts_error(monkeypatch):
    model = StalledModel()
    monkeypatch.setattr("expense_intelligence.agent.runtime.build_model", lambda _: model)
    started = perf_counter()
    with pytest.raises(RuntimeError, match="temporarily unavailable") as error:
        run_agent(Settings(agent_mode="synthetic_developer", agent_total_timeout_seconds=1), "Synthetic question", [])
    assert perf_counter() - started < 2
    assert model.cancelled
    assert "timeout" not in str(error.value).lower()


def test_openrouter_transport_has_explicit_timeouts_no_retries(monkeypatch):
    captured = {}
    class FakeClient:
        def __init__(self, **kwargs): captured.setdefault("clients", []).append(kwargs)
    class FakeAsyncClient(FakeClient): pass
    class FakeChat:
        def __init__(self, **kwargs): captured.update(kwargs)
    monkeypatch.setattr("expense_intelligence.agent.providers.httpx2.Client", FakeClient)
    monkeypatch.setattr("expense_intelligence.agent.providers.httpx2.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("expense_intelligence.agent.providers.ChatOpenAI", FakeChat)
    from expense_intelligence.agent.providers import build_model
    build_model(Settings(agent_provider="openrouter", openrouter_api_key="synthetic", agent_timeout_seconds=7, agent_max_retries=0))
    assert captured["max_retries"] == 0 and captured["streaming"] is False
    assert captured["extra_body"] == {"reasoning": {"enabled": False, "exclude": True}}
    assert len(captured["clients"]) == 2
