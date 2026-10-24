"""Add visual preferences and private beta feedback details."""

import sqlalchemy as sa
from alembic import op

revision = "0014_beta_refinement"
down_revision = "0013_group_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    preferences = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user_preferences")}
    with op.batch_alter_table("user_preferences") as batch:
        if "theme" not in preferences:
            batch.add_column(sa.Column("theme", sa.String(12), nullable=False, server_default="system"))
        if "accent" not in preferences:
            batch.add_column(sa.Column("accent", sa.String(12), nullable=False, server_default="ocean"))
    feedback = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("product_feedback")}
    with op.batch_alter_table("product_feedback") as batch:
        for name, column in {
            "description": sa.Column("description", sa.String(2000), nullable=True),
            "steps": sa.Column("steps", sa.String(2000), nullable=True),
            "page_path": sa.Column("page_path", sa.String(300), nullable=True),
            "viewport": sa.Column("viewport", sa.String(32), nullable=True),
            "contact_allowed": sa.Column("contact_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
            "screenshot_data": sa.Column("screenshot_data", sa.Text(), nullable=True),
        }.items():
            if name not in feedback:
                batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("product_feedback") as batch:
        for name in ["screenshot_data", "contact_allowed", "viewport", "page_path", "steps", "description"]:
            batch.drop_column(name)
    with op.batch_alter_table("user_preferences") as batch:
        batch.drop_column("accent")
        batch.drop_column("theme")
