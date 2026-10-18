from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import FeatureFlag


class FlagName(StrEnum):
    CHAT_HISTORY = "CHAT_HISTORY"
    SHORT_TERM_MEMORY = "SHORT_TERM_MEMORY"
    LONG_TERM_MEMORY = "LONG_TERM_MEMORY"


DEFAULT_FLAGS = {
    FlagName.CHAT_HISTORY: (False, "Persist user-scoped chat threads and messages"),
    FlagName.SHORT_TERM_MEMORY: (False, "Use bounded thread context and checkpoints"),
    FlagName.LONG_TERM_MEMORY: (False, "Use explicit user-controlled persistent memories"),
}


def seed_flags(session: Session) -> None:
    for name, (enabled, description) in DEFAULT_FLAGS.items():
        if session.get(FeatureFlag, name.value) is None:
            session.add(FeatureFlag(name=name.value, enabled=enabled, description=description))
    session.commit()


def is_enabled(session: Session, name: FlagName) -> bool:
    value = session.scalar(select(FeatureFlag.enabled).where(FeatureFlag.name == name.value))
    return bool(value)
