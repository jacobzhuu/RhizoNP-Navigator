"""add literature corpus revision singleton state

Revision ID: 0003_literature_corpus_state
Revises: 0002_literature_provenance
Create Date: 2026-07-06 16:50:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_literature_corpus_state"
down_revision = "0002_literature_provenance"
branch_labels = None
depends_on = None

_CORPUS_STATE_ID = 1


def upgrade() -> None:
    op.create_table(
        "literature_corpus_state",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("corpus_revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("content_checksum", sa.Text(), nullable=True),
        sa.Column("ordered_chunk_ids_checksum", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_literature_corpus_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO literature_corpus_state "
            "(id, corpus_revision, chunk_count, content_checksum, ordered_chunk_ids_checksum) "
            "VALUES (:id, 0, 0, NULL, NULL)"
        ).bindparams(id=_CORPUS_STATE_ID)
    )


def downgrade() -> None:
    op.drop_table("literature_corpus_state")
