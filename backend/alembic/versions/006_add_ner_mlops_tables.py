"""Add NER MLOps tables (ner_training_samples, ner_model_versions)

Revision ID: 006_ner_mlops
Revises: 005_input_article
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "006_ner_mlops"
down_revision = "005_input_article"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ner_training_samples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("bio_tags", JSONB, nullable=False),
        sa.Column("gpt_quality_score", sa.Float(), nullable=False),
        sa.Column("gpt_corrected_entities", JSONB, nullable=False),
        sa.Column("gpt_reasoning", sa.Text(), nullable=True),
        sa.Column("extraction_model_version", sa.String(20), nullable=True),
        sa.Column("extraction_method", sa.String(20), nullable=True),
        sa.Column("is_used_for_training", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ner_model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version", sa.String(20), unique=True, nullable=False),
        sa.Column("base_model", sa.String(100), nullable=True),
        sa.Column("model_path", sa.Text(), nullable=True),
        sa.Column("training_samples_count", sa.Integer(), nullable=True),
        sa.Column("eval_f1_score", sa.Float(), nullable=True),
        sa.Column("eval_precision", sa.Float(), nullable=True),
        sa.Column("eval_recall", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'training'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ner_model_versions")
    op.drop_table("ner_training_samples")
