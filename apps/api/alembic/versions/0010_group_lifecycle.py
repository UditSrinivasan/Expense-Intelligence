"""Add reversible group archiving."""

import sqlalchemy as sa
from alembic import op

revision = "0010_group_lifecycle"
down_revision = "0009_user_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("expense_groups")}
    if "archived_at" not in columns:
        op.add_column("expense_groups", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_expense_groups_archived_at", "expense_groups", ["archived_at"])


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("expense_groups")}
    if "archived_at" in columns:
        op.drop_index("ix_expense_groups_archived_at", table_name="expense_groups")
        op.drop_column("expense_groups", "archived_at")
