import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from expense_intelligence.models import ChatCheckpoint, ChatThread, User, UserMemory


def test_chat_and_memory_records_are_owned_independently(db):
    first = User(auth_subject="test:first")
    second = User(auth_subject="test:second")
    db.add_all([first, second])
    db.flush()
    thread = ChatThread(owner_user_id=first.id, title="October spending")
    memory = UserMemory(
        owner_user_id=first.id,
        memory_type="reporting_preference",
        content_json='{"currency":"GBP"}',
        provenance="explicit_user_request",
    )
    db.add_all([thread, memory])
    db.flush()
    db.add(
        ChatCheckpoint(
            owner_user_id=first.id,
            thread_id=thread.id,
            workflow_version="demo-v1",
            state_json='{"summary":"synthetic only"}',
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    db.commit()

    visible_to_second = db.scalars(select(UserMemory).where(UserMemory.owner_user_id == second.id)).all()
    assert visible_to_second == []
    assert db.scalar(select(ChatThread).where(ChatThread.owner_user_id == first.id)).id == thread.id
