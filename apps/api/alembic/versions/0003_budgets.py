"""Add owner-scoped budgets and immutable budget revisions."""

from alembic import op
import sqlalchemy as sa

from expense_intelligence import models

revision = "0003_budgets"
down_revision = "0002_categories_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in (models.Budget.__table__, models.BudgetRevision.__table__):
        if table.name not in existing:
            table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    for table in (models.BudgetRevision.__table__, models.Budget.__table__):
        table.drop(bind=op.get_bind(), checkfirst=True)
