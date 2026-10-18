"""Initial financial, audit, chat and memory schema."""

from alembic import op

from expense_intelligence.database import Base
from expense_intelligence import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.bulk_insert(
        models.FeatureFlag.__table__,
        [
            {"name": "CHAT_HISTORY", "enabled": False, "description": "Persist user-scoped chat threads and messages"},
            {"name": "SHORT_TERM_MEMORY", "enabled": False, "description": "Use bounded thread context and checkpoints"},
            {"name": "LONG_TERM_MEMORY", "enabled": False, "description": "Use explicit user-controlled persistent memories"},
        ],
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
