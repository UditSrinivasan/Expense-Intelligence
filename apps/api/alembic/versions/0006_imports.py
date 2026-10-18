"""Add browser-local structured import staging and transaction provenance."""

from alembic import op
import sqlalchemy as sa
from expense_intelligence import models

revision = "0006_imports"
down_revision = "0005_group_finance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind(); inspector = sa.inspect(bind); existing = set(inspector.get_table_names())
    for table in (models.FinancialAccount.__table__, models.ImportBatch.__table__, models.ImportRow.__table__, models.ImportMappingProfile.__table__):
        if table.name not in existing: table.create(bind=bind, checkfirst=True)
    columns = {column["name"] for column in sa.inspect(bind).get_columns("transactions")}
    if "account_id" not in columns:
        with op.batch_alter_table("transactions") as batch:
            batch.add_column(sa.Column("account_id", sa.Uuid(), nullable=True)); batch.add_column(sa.Column("import_batch_id", sa.Uuid(), nullable=True)); batch.add_column(sa.Column("import_row_id", sa.Uuid(), nullable=True)); batch.add_column(sa.Column("posting_date", sa.Date(), nullable=True)); batch.add_column(sa.Column("source_reference", sa.String(160), nullable=True))
            batch.create_foreign_key("fk_transaction_account", "financial_accounts", ["account_id"], ["id"]); batch.create_foreign_key("fk_transaction_import_batch", "import_batches", ["import_batch_id"], ["id"]); batch.create_foreign_key("fk_transaction_import_row", "import_rows", ["import_row_id"], ["id"])
            batch.create_index("ix_transactions_account_id", ["account_id"]); batch.create_index("ix_transactions_import_batch_id", ["import_batch_id"]); batch.create_index("ix_transactions_import_row_id", ["import_row_id"], unique=True); batch.create_index("ix_transactions_source_reference", ["source_reference"])


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.drop_index("ix_transactions_source_reference")
        batch.drop_index("ix_transactions_import_row_id")
        batch.drop_index("ix_transactions_import_batch_id")
        batch.drop_index("ix_transactions_account_id")
        for name in (
            "source_reference",
            "posting_date",
            "import_row_id",
            "import_batch_id",
            "account_id",
        ):
            batch.drop_column(name)
    for table in (
        models.ImportMappingProfile.__table__,
        models.ImportRow.__table__,
        models.ImportBatch.__table__,
        models.FinancialAccount.__table__,
    ):
        table.drop(bind=op.get_bind(), checkfirst=True)
