"""Add receipt provenance and component-level attribution."""

import sqlalchemy as sa
from alembic import op

revision = "0011_receipt_split_attribution"
down_revision = "0010_group_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    shared_columns = {column["name"] for column in inspector.get_columns("shared_expenses")}
    with op.batch_alter_table("shared_expenses") as batch:
        if "source_receipt_id" not in shared_columns:
            batch.add_column(sa.Column("source_receipt_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_shared_expense_receipt", "receipt_documents", ["source_receipt_id"], ["id"], ondelete="RESTRICT")
            batch.create_index("ix_shared_expenses_source_receipt_id", ["source_receipt_id"], unique=True)
        if "linked_transaction_id" not in shared_columns:
            batch.add_column(sa.Column("linked_transaction_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_shared_expense_transaction", "transactions", ["linked_transaction_id"], ["id"], ondelete="RESTRICT")
            batch.create_index("ix_shared_expenses_linked_transaction_id", ["linked_transaction_id"])
    component_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("expense_components")}
    if "category_id" not in component_columns:
        with op.batch_alter_table("expense_components") as batch:
            batch.add_column(sa.Column("category_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_expense_component_category", "categories", ["category_id"], ["id"], ondelete="RESTRICT")
            batch.create_index("ix_expense_components_category_id", ["category_id"])


def downgrade() -> None:
    with op.batch_alter_table("expense_components") as batch:
        batch.drop_column("category_id")
    with op.batch_alter_table("shared_expenses") as batch:
        batch.drop_column("linked_transaction_id")
        batch.drop_column("source_receipt_id")
