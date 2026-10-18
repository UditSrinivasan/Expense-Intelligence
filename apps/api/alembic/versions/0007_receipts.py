"""Add reviewed receipt documents and transaction links."""

from alembic import op
from expense_intelligence import models


revision = "0007_receipts"
down_revision = "0006_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    models.ReceiptDocument.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    models.ReceiptDocument.__table__.drop(bind=op.get_bind(), checkfirst=True)
