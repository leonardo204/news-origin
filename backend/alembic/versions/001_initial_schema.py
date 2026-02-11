"""Initial schema - articles, tracking_requests, timeline_entries, search_logs

Revision ID: 001_initial
Revises:
Create Date: 2025-02-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Articles
    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("publisher_domain", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(10), server_default="ko"),
        sa.Column(
            "qdrant_point_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_articles_url", "articles", ["url"], unique=True)
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_qdrant_point_id", "articles", ["qdrant_point_id"])
    op.create_index("idx_articles_publisher", "articles", ["publisher"])

    # Tracking Requests
    op.create_table(
        "tracking_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("input_type", sa.String(10), nullable=False),
        sa.Column(
            "origin_article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("total_articles", sa.Integer(), server_default="0"),
        sa.Column("progress", sa.Integer(), server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Timeline Entries
    op.create_table(
        "timeline_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tracking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracking_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id"),
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("similarity_category", sa.String(20), nullable=True),
        sa.Column("lifecycle_stage", sa.String(20), nullable=True),
        sa.Column(
            "parent_article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id"),
            nullable=True,
        ),
        sa.Column("is_origin", sa.Boolean(), server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tracking_id", "article_id", name="uq_tracking_article"),
    )
    op.create_index(
        "ix_timeline_entries_tracking_id", "timeline_entries", ["tracking_id"]
    )
    op.create_index(
        "ix_timeline_entries_lifecycle_stage",
        "timeline_entries",
        ["lifecycle_stage"],
    )

    # Search Logs
    op.create_table(
        "search_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("input_type", sa.String(10), nullable=True),
        sa.Column("result_count", sa.Integer(), server_default="0"),
        sa.Column(
            "tracking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracking_requests.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("search_logs")
    op.drop_table("timeline_entries")
    op.drop_table("tracking_requests")
    op.drop_table("articles")
