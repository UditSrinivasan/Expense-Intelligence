"""Add universal group splitting foundation."""

from alembic import op
import sqlalchemy as sa
from expense_intelligence import models

revision = "0004_group_splitting"
down_revision = "0003_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in (models.ExpenseGroup.__table__, models.GroupMember.__table__, models.SharedExpense.__table__, models.ExpensePayer.__table__, models.ExpenseComponent.__table__, models.ExpenseAllocation.__table__):
        if table.name not in existing:
            table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    for table in (models.ExpenseAllocation.__table__, models.ExpenseComponent.__table__, models.ExpensePayer.__table__, models.SharedExpense.__table__, models.GroupMember.__table__, models.ExpenseGroup.__table__):
        table.drop(bind=op.get_bind(), checkfirst=True)
