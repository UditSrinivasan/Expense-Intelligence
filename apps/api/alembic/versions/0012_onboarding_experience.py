"""Persist the user-scoped product tour, checklist, and privacy-safe feedback."""

import sqlalchemy as sa
from alembic import op

revision = "0012_onboarding_experience"
down_revision = "0011_receipt_split_attribution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user_preferences")}
    with op.batch_alter_table("user_preferences") as batch:
        if "tour_state" not in columns:
            batch.add_column(sa.Column("tour_state", sa.String(20), nullable=False, server_default="never_started"))
        if "tour_step" not in columns:
            batch.add_column(sa.Column("tour_step", sa.Integer(), nullable=False, server_default="0"))
        if "checklist_dismissed" not in columns:
            batch.add_column(sa.Column("checklist_dismissed", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "dashboard_reviewed_at" not in columns:
            batch.add_column(sa.Column("dashboard_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    if "product_feedback" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "product_feedback",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("sentiment", sa.String(16), nullable=False),
            sa.Column("target_id", sa.String(80), nullable=True),
            sa.Column("reason", sa.String(40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("product_feedback")}
    if "ix_product_feedback_owner_user_id" not in indexes:
        op.create_index("ix_product_feedback_owner_user_id", "product_feedback", ["owner_user_id"])
    if "ix_product_feedback_owner_created" not in indexes:
        op.create_index("ix_product_feedback_owner_created", "product_feedback", ["owner_user_id", "created_at"])


def downgrade() -> None:
    if "product_feedback" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("product_feedback")
    with op.batch_alter_table("user_preferences") as batch:
        batch.drop_column("dashboard_reviewed_at")
        batch.drop_column("checklist_dismissed")
        batch.drop_column("tour_step")
        batch.drop_column("tour_state")
