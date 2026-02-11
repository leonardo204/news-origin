"""Add error_message to tracking_requests

Revision ID: 002_error_msg
Revises: 001_initial
Create Date: 2025-02-11

"""
from alembic import op
import sqlalchemy as sa

revision = "002_error_msg"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracking_requests",
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracking_requests", "error_message")
