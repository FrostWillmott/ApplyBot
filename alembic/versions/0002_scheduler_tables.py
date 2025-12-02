"""Add scheduler tables

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create scheduler_settings table
    op.create_table(
        'scheduler_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('schedule_hour', sa.Integer(), nullable=False, default=9),
        sa.Column('schedule_minute', sa.Integer(), nullable=False, default=0),
        sa.Column('schedule_days', sa.String(length=50), nullable=False, default='mon,tue,wed,thu,fri'),
        sa.Column('timezone', sa.String(length=50), nullable=False, default='Europe/Moscow'),
        sa.Column('max_applications_per_run', sa.Integer(), nullable=False, default=10),
        sa.Column('resume_id', sa.String(length=255), nullable=True),
        sa.Column('search_criteria', sa.JSON(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_status', sa.String(length=50), nullable=True),
        sa.Column('last_run_applications', sa.Integer(), default=0),
        sa.Column('total_applications', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduler_settings_user_id', 'scheduler_settings', ['user_id'], unique=True)

    # Create scheduler_run_history table
    op.create_table(
        'scheduler_run_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('applications_sent', sa.Integer(), default=0),
        sa.Column('applications_skipped', sa.Integer(), default=0),
        sa.Column('applications_failed', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduler_run_history_user_id', 'scheduler_run_history', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_scheduler_run_history_user_id', table_name='scheduler_run_history')
    op.drop_table('scheduler_run_history')
    op.drop_index('ix_scheduler_settings_user_id', table_name='scheduler_settings')
    op.drop_table('scheduler_settings')

