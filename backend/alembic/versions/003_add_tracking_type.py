"""Add tracking_type to tracking_requests

Revision ID: 003_tracking_type
Revises: 002_error_msg
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa

revision = "003_tracking_type"
down_revision = "002_error_msg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracking_requests",
        sa.Column(
            "tracking_type",
            sa.String(10),
            server_default="instant",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tracking_requests", "tracking_type")
