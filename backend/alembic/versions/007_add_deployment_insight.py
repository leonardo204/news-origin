"""Add deployment_insight column to ner_model_versions

Revision ID: 007_deployment_insight
Revises: 006_ner_mlops
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa

revision = "007_deployment_insight"
down_revision = "006_ner_mlops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ner_model_versions",
        sa.Column("deployment_insight", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ner_model_versions", "deployment_insight")
