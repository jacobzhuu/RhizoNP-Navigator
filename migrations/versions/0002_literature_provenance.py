"""add phase 2 literature provenance tables

Revision ID: 0002_literature_provenance
Revises: 0001_domain_schema
Create Date: 2026-07-05 13:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_literature_provenance"
down_revision = "0001_domain_schema"
branch_labels = None
depends_on = None


def json_type() -> sa.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def uuid_type() -> sa.TypeEngine:
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "paper_chunks",
        sa.Column("chunk_id", uuid_type(), nullable=False),
        sa.Column("paper_id", uuid_type(), nullable=False),
        sa.Column("section", sa.String(length=64), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.paper_id"]),
        sa.PrimaryKeyConstraint("chunk_id"),
        sa.UniqueConstraint(
            "paper_id",
            "source_hash",
            "char_start",
            "char_end",
            name="uq_paper_chunk_source_span",
        ),
    )
    op.create_index("idx_paper_chunks_paper", "paper_chunks", ["paper_id"])
    op.create_index("idx_paper_chunks_section", "paper_chunks", ["section"])
    op.create_index("idx_paper_chunks_source_hash", "paper_chunks", ["source_hash"])

    op.create_table(
        "retrieval_runs",
        sa.Column("run_id", uuid_type(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("retrieval_mode", sa.String(length=64), nullable=False),
        sa.Column("filters", json_type(), nullable=False),
        sa.Column("parameters", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )

    op.create_table(
        "retrieval_results",
        sa.Column("result_id", uuid_type(), nullable=False),
        sa.Column("run_id", uuid_type(), nullable=False),
        sa.Column("chunk_id", uuid_type(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("score_components", json_type(), nullable=False),
        sa.Column("matched_terms", json_type(), nullable=False),
        sa.Column("provenance", json_type(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["paper_chunks.chunk_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["retrieval_runs.run_id"]),
        sa.PrimaryKeyConstraint("result_id"),
        sa.UniqueConstraint("run_id", "rank", name="uq_retrieval_result_run_rank"),
    )
    op.create_index("idx_retrieval_results_chunk", "retrieval_results", ["chunk_id"])
    op.create_index("idx_retrieval_results_run_rank", "retrieval_results", ["run_id", "rank"])


def downgrade() -> None:
    op.drop_index("idx_retrieval_results_run_rank", table_name="retrieval_results")
    op.drop_index("idx_retrieval_results_chunk", table_name="retrieval_results")
    op.drop_table("retrieval_results")
    op.drop_table("retrieval_runs")
    op.drop_index("idx_paper_chunks_source_hash", table_name="paper_chunks")
    op.drop_index("idx_paper_chunks_section", table_name="paper_chunks")
    op.drop_index("idx_paper_chunks_paper", table_name="paper_chunks")
    op.drop_table("paper_chunks")
