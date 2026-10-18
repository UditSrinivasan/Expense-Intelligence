"""Add explainable analytics state."""

from alembic import op
from expense_intelligence import models

revision = "0008_analytics"
down_revision = "0007_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    models.InsightRecord.__table__.create(bind=bind, checkfirst=True)
    models.AnalyticsPreference.__table__.create(bind=bind, checkfirst=True)
    models.RecurringDecision.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    models.RecurringDecision.__table__.drop(bind=bind, checkfirst=True)
    models.AnalyticsPreference.__table__.drop(bind=bind, checkfirst=True)
    models.InsightRecord.__table__.drop(bind=bind, checkfirst=True)
