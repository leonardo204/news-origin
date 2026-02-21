"""Add original_entities column to ner_training_samples

Revision ID: 008_original_entities
Revises: 007_deployment_insight
Create Date: 2026-02-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008_original_entities"
down_revision = "007_deployment_insight"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ner_training_samples",
        sa.Column("original_entities", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ner_training_samples", "original_entities")
