"""Add hierarchical categories, exact user rules and reconciled allocations."""

from alembic import op
import sqlalchemy as sa

from expense_intelligence import models

revision = "0002_categories_learning"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table in (models.Category.__table__, models.CategoryAlias.__table__, models.Merchant.__table__, models.MerchantAlias.__table__, models.ClassificationRule.__table__, models.TransactionAllocation.__table__):
        if table.name not in existing_tables:
            table.create(bind=bind, checkfirst=True)

    columns = {column["name"] for column in sa.inspect(bind).get_columns("transactions")}
    additions = [
        sa.Column("raw_description", sa.String(500)),
        sa.Column("normalized_description", sa.String(280)),
        sa.Column("merchant_id", sa.Uuid()),
        sa.Column("category_id", sa.Uuid()),
        sa.Column("transaction_type", sa.String(24), nullable=False, server_default="purchase"),
        sa.Column("classification_source", sa.String(24), nullable=False, server_default="unclassified"),
        sa.Column("classification_confidence", sa.Float()),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]
    with op.batch_alter_table("transactions") as batch:
        for column in additions:
            if column.name not in columns:
                batch.add_column(column)


def downgrade() -> None:
    columns = ["raw_description", "normalized_description", "merchant_id", "category_id", "transaction_type", "classification_source", "classification_confidence", "needs_review"]
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("transactions")}
    with op.batch_alter_table("transactions") as batch:
        for name in columns:
            if name in existing:
                batch.drop_column(name)
    for table in (models.TransactionAllocation.__table__, models.ClassificationRule.__table__, models.MerchantAlias.__table__, models.Merchant.__table__, models.CategoryAlias.__table__, models.Category.__table__):
        table.drop(bind=op.get_bind(), checkfirst=True)
