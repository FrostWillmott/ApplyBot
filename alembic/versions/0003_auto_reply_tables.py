"""Add auto-reply settings and history tables.

Revision ID: 0003
Revises: 0002
Create Date: 2025-12-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create auto_reply_settings table
    op.create_table(
        "auto_reply_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("check_interval_minutes", sa.Integer(), nullable=False, default=60),
        sa.Column("timezone", sa.String(50), nullable=False, default="Europe/Moscow"),
        sa.Column("active_hours_start", sa.Integer(), nullable=False, default=9),
        sa.Column("active_hours_end", sa.Integer(), nullable=False, default=21),
        sa.Column(
            "active_days",
            sa.String(50),
            nullable=False,
            default="mon,tue,wed,thu,fri,sat,sun",
        ),
        sa.Column("auto_send", sa.Boolean(), nullable=False, default=False),
        sa.Column("last_check_at", sa.DateTime(), nullable=True),
        sa.Column("total_replies_sent", sa.Integer(), nullable=False, default=0),
        sa.Column("total_messages_processed", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auto_reply_settings_user_id", "auto_reply_settings", ["user_id"], unique=True
    )

    # Create auto_reply_history table
    op.create_table(
        "auto_reply_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("negotiation_id", sa.String(255), nullable=False),
        sa.Column("vacancy_id", sa.String(255), nullable=True),
        sa.Column("employer_message", sa.Text(), nullable=False),
        sa.Column("generated_reply", sa.Text(), nullable=False),
        sa.Column("was_sent", sa.Boolean(), nullable=False, default=False),
        sa.Column("employer_name", sa.String(500), nullable=True),
        sa.Column("vacancy_title", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auto_reply_history_user_id", "auto_reply_history", ["user_id"], unique=False
    )
    op.create_index(
        "ix_auto_reply_history_negotiation_id",
        "auto_reply_history",
        ["negotiation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auto_reply_history_negotiation_id", table_name="auto_reply_history")
    op.drop_index("ix_auto_reply_history_user_id", table_name="auto_reply_history")
    op.drop_table("auto_reply_history")

    op.drop_index("ix_auto_reply_settings_user_id", table_name="auto_reply_settings")
    op.drop_table("auto_reply_settings")
