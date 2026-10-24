"""Add expiring, revocable guest-to-account invitations."""

import sqlalchemy as sa
from alembic import op

revision = "0013_group_invitations"
down_revision = "0012_onboarding_experience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "group_invitations" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "group_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("expense_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guest_member_id", sa.Uuid(), sa.ForeignKey("group_members.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invited_email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_group_invitations_group_id", "group_invitations", ["group_id"])
    op.create_index("ix_group_invitations_guest_member_id", "group_invitations", ["guest_member_id"])
    op.create_index("ix_group_invitations_token_hash", "group_invitations", ["token_hash"], unique=True)
    op.create_index("ix_group_invitations_expires_at", "group_invitations", ["expires_at"])
    op.create_index("ix_group_invitations_group_email", "group_invitations", ["group_id", "invited_email"])


def downgrade() -> None:
    if "group_invitations" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("group_invitations")
