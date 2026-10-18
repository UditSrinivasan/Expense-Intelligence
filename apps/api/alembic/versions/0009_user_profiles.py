"""Add onboarding fields to user preferences."""

import sqlalchemy as sa
from alembic import op

revision = "0009_user_profiles"
down_revision = "0008_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user_preferences")}
    if "display_name" not in columns:
        op.add_column("user_preferences", sa.Column("display_name", sa.String(120), nullable=False, server_default=""))
    if "onboarding_completed" not in columns:
        op.add_column("user_preferences", sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user_preferences")}
    if "onboarding_completed" in columns:
        op.drop_column("user_preferences", "onboarding_completed")
    if "display_name" in columns:
        op.drop_column("user_preferences", "display_name")
