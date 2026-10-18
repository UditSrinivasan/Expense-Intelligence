"""Add settlements, reusable split templates and expense correction metadata."""

from alembic import op
import sqlalchemy as sa
from expense_intelligence import models

revision = "0005_group_finance"
down_revision = "0004_group_splitting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("shared_expenses")}
    if "category_id" not in columns:
        with op.batch_alter_table("shared_expenses") as batch:
            batch.add_column(sa.Column("category_id", sa.Uuid(), nullable=True))
            batch.add_column(sa.Column("corrects_expense_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_shared_expense_category", "categories", ["category_id"], ["id"])
            batch.create_foreign_key("fk_shared_expense_correction", "shared_expenses", ["corrects_expense_id"], ["id"])
            batch.create_index("ix_shared_expenses_category_id", ["category_id"])
            batch.create_index("ix_shared_expenses_corrects_expense_id", ["corrects_expense_id"])
    existing = set(inspector.get_table_names())
    for table in (models.Settlement.__table__, models.SplitTemplate.__table__):
        if table.name not in existing:
            table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    models.SplitTemplate.__table__.drop(bind=op.get_bind(), checkfirst=True)
    models.Settlement.__table__.drop(bind=op.get_bind(), checkfirst=True)
    with op.batch_alter_table("shared_expenses") as batch:
        batch.drop_column("corrects_expense_id")
        batch.drop_column("category_id")
