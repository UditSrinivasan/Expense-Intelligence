import uuid
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agent.runtime import AgentResult, run_agent
from .config import Settings
from .flags import FlagName, is_enabled
from .models import ChatMessage, ChatThread, UserMemory


def _owned_thread(session: Session, owner_id: uuid.UUID, thread_id: uuid.UUID) -> ChatThread | None:
    return session.scalar(select(ChatThread).where(ChatThread.id == thread_id, ChatThread.owner_user_id == owner_id, ChatThread.deleted_at.is_(None)))


def list_threads(session: Session, owner_id: uuid.UUID) -> list[ChatThread]:
    return list(session.scalars(select(ChatThread).where(ChatThread.owner_user_id == owner_id, ChatThread.deleted_at.is_(None)).order_by(ChatThread.updated_at.desc())).all())


def list_messages(session: Session, owner_id: uuid.UUID, thread_id: uuid.UUID, limit: int = 100) -> list[ChatMessage]:
    if not _owned_thread(session, owner_id, thread_id):
        return []
    rows = session.scalars(select(ChatMessage).where(ChatMessage.owner_user_id == owner_id, ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at.desc()).limit(limit)).all()
    return list(reversed(rows))


def chat(session: Session, settings: Settings, owner_id: uuid.UUID, prompt: str, thread_id: uuid.UUID | None) -> tuple[uuid.UUID, ChatMessage, AgentResult]:
    history_enabled = is_enabled(session, FlagName.CHAT_HISTORY)
    memory_enabled = is_enabled(session, FlagName.SHORT_TERM_MEMORY)
    thread = _owned_thread(session, owner_id, thread_id) if thread_id else None
    if thread_id and not thread:
        raise LookupError("Conversation not found")
    if history_enabled and not thread:
        thread = ChatThread(owner_user_id=owner_id, title=prompt[:80])
        session.add(thread)
        session.flush()
    active_id = thread.id if thread else uuid.uuid4()
    previous: list[tuple[str, str]] = []
    if history_enabled and memory_enabled and thread:
        previous = [(row.role, row.content) for row in list_messages(session, owner_id, thread.id, settings.agent_history_messages)]
    synthetic_memory = None
    if is_enabled(session, FlagName.LONG_TERM_MEMORY):
        memory = session.scalar(select(UserMemory).where(UserMemory.owner_user_id == owner_id, UserMemory.memory_type == "synthetic_demo_preference", UserMemory.deleted_at.is_(None)).order_by(UserMemory.updated_at.desc()))
        if memory:
            values = json.loads(memory.content_json)
            synthetic_memory = f"Preferred currency: {values['preferred_currency']}; response style: {values['response_style']}."
    result = run_agent(settings, prompt, previous, synthetic_memory)
    if history_enabled and thread:
        session.add(ChatMessage(owner_user_id=owner_id, thread_id=thread.id, role="user", content=prompt))
        # Persist the user turn first so databases are not asked to infer order
        # between two rows that an INSERT batch may give the same timestamp.
        session.flush()
        reply = ChatMessage(owner_user_id=owner_id, thread_id=thread.id, role="assistant", content=result.content)
        session.add(reply)
        thread.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(reply)
    else:
        reply = ChatMessage(id=uuid.uuid4(), owner_user_id=owner_id, thread_id=active_id, role="assistant", content=result.content, created_at=datetime.now(timezone.utc))
    return active_id, reply, result
