"""add interaction history table

Revision ID: 0004_interaction_history
Revises: 0003_literature_corpus_state
Create Date: 2026-07-07 02:10:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_interaction_history"
down_revision = "0003_literature_corpus_state"
branch_labels = None
depends_on = None


def json_type() -> sa.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def uuid_type() -> sa.TypeEngine:
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "interaction_history",
        sa.Column("history_id", uuid_type(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("request_payload", json_type(), nullable=False),
        sa.Column("response_payload", json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index(
        "idx_interaction_history_kind_created",
        "interaction_history",
        ["kind", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_interaction_history_kind_created", table_name="interaction_history")
    op.drop_table("interaction_history")
