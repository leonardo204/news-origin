"""add metric_type column to ner_model_versions

Revision ID: 012_add_metric_type
Revises: 011_articles_created_at_idx
Create Date: 2026-02-24
"""

import sqlalchemy as sa
from alembic import op

revision = "012_add_metric_type"
down_revision = "011_articles_created_at_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ner_model_versions",
        sa.Column("metric_type", sa.String(20), nullable=True),
    )


def downgrade():
    op.drop_column("ner_model_versions", "metric_type")
