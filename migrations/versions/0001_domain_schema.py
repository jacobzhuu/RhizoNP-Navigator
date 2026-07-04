"""create phase 1 domain schema

Revision ID: 0001_domain_schema
Revises:
Create Date: 2026-07-05 02:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_domain_schema"
down_revision = None
branch_labels = None
depends_on = None


def json_type() -> sa.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def uuid_type() -> sa.TypeEngine:
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "papers",
        sa.Column("paper_id", uuid_type(), nullable=False),
        sa.Column("doi", sa.Text(), nullable=True),
        sa.Column("pmid", sa.Text(), nullable=True),
        sa.Column("pmcid", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("journal", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("provenance", json_type(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("paper_id"),
        sa.UniqueConstraint("doi"),
    )
    op.create_table(
        "taxa",
        sa.Column("taxon_id", uuid_type(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("rank", sa.String(length=64), nullable=True),
        sa.Column("strain", sa.Text(), nullable=True),
        sa.Column("species", sa.Text(), nullable=True),
        sa.Column("genus", sa.Text(), nullable=True),
        sa.Column("family", sa.Text(), nullable=True),
        sa.Column("external_ids", json_type(), nullable=False),
        sa.Column("normalization_status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("taxon_id"),
    )
    op.create_index("idx_taxa_canonical_name_lower", "taxa", [sa.text("lower(canonical_name)")])
    op.create_table(
        "compounds",
        sa.Column("compound_id", uuid_type(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("smiles", sa.Text(), nullable=True),
        sa.Column("inchikey", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("compound_class", sa.Text(), nullable=True),
        sa.Column("structure_status", sa.String(length=64), nullable=False),
        sa.Column("external_ids", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("compound_id"),
    )
    op.create_index("idx_compounds_canonical_name_lower", "compounds", [sa.text("lower(canonical_name)")])
    op.create_index("idx_compounds_inchikey", "compounds", ["inchikey"])
    op.create_table(
        "datasets",
        sa.Column("dataset_id", uuid_type(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("data_type", sa.String(length=128), nullable=False),
        sa.Column("provenance", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("dataset_id"),
    )
    op.create_table(
        "candidate_links",
        sa.Column("candidate_id", uuid_type(), nullable=False),
        sa.Column("source_entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", uuid_type(), nullable=False),
        sa.Column("relation", sa.String(length=128), nullable=False),
        sa.Column("target_entity_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_id", uuid_type(), nullable=False),
        sa.Column("internal_evidence_score", sa.Float(), nullable=True),
        sa.Column("external_evidence_score", sa.Float(), nullable=True),
        sa.Column("taxonomy_distance", sa.String(length=64), nullable=True),
        sa.Column("evidence_tier", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("rationale", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("candidate_id"),
    )
    op.create_index("idx_candidate_links_source", "candidate_links", ["source_entity_type", "source_entity_id"])
    op.create_index("idx_candidate_links_status", "candidate_links", ["status"])
    op.create_table(
        "evidence_items",
        sa.Column("evidence_id", uuid_type(), nullable=False),
        sa.Column("claim_type", sa.String(length=128), nullable=False),
        sa.Column("subject_entity_type", sa.String(length=64), nullable=False),
        sa.Column("subject_entity_id", uuid_type(), nullable=False),
        sa.Column("predicate", sa.String(length=128), nullable=False),
        sa.Column("object_entity_type", sa.String(length=64), nullable=True),
        sa.Column("object_entity_id", uuid_type(), nullable=True),
        sa.Column("object_literal", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", uuid_type(), nullable=False),
        sa.Column("evidence_tier", sa.String(length=64), nullable=False),
        sa.Column("directness", sa.String(length=64), nullable=False),
        sa.Column("extraction_method", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting_span", sa.Text(), nullable=True),
        sa.Column("provenance", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    op.create_index("idx_evidence_source", "evidence_items", ["source_type", "source_id"])
    op.create_index("idx_evidence_subject", "evidence_items", ["subject_entity_type", "subject_entity_id"])
    op.create_table(
        "natural_product_records",
        sa.Column("np_record_id", uuid_type(), nullable=False),
        sa.Column("compound_id", uuid_type(), nullable=False),
        sa.Column("producer_taxon_id", uuid_type(), nullable=True),
        sa.Column("source_database", sa.Text(), nullable=False),
        sa.Column("external_record_id", sa.Text(), nullable=False),
        sa.Column("bioactivity_summary", sa.Text(), nullable=True),
        sa.Column("reference_paper_id", uuid_type(), nullable=True),
        sa.Column("provenance", json_type(), nullable=False),
        sa.ForeignKeyConstraint(["compound_id"], ["compounds.compound_id"]),
        sa.ForeignKeyConstraint(["producer_taxon_id"], ["taxa.taxon_id"]),
        sa.ForeignKeyConstraint(["reference_paper_id"], ["papers.paper_id"]),
        sa.PrimaryKeyConstraint("np_record_id"),
        sa.UniqueConstraint("source_database", "external_record_id", name="uq_np_source_record"),
    )
    op.create_table(
        "omics_associations",
        sa.Column("association_id", uuid_type(), nullable=False),
        sa.Column("dataset_id", uuid_type(), nullable=False),
        sa.Column("source_entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_entity_id", uuid_type(), nullable=True),
        sa.Column("source_raw_label", sa.Text(), nullable=False),
        sa.Column("target_entity_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_id", uuid_type(), nullable=True),
        sa.Column("target_raw_label", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("adjusted_p", sa.Float(), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(length=64), nullable=True),
        sa.Column("treatment", sa.Text(), nullable=True),
        sa.Column("timepoint", sa.Text(), nullable=True),
        sa.Column("metadata", json_type(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.dataset_id"]),
        sa.PrimaryKeyConstraint("association_id"),
    )
    op.create_table(
        "omics_observations",
        sa.Column("observation_id", uuid_type(), nullable=False),
        sa.Column("dataset_id", uuid_type(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", uuid_type(), nullable=True),
        sa.Column("raw_label", sa.Text(), nullable=False),
        sa.Column("treatment", sa.Text(), nullable=True),
        sa.Column("timepoint", sa.Text(), nullable=True),
        sa.Column("layer", sa.Text(), nullable=True),
        sa.Column("effect_size", sa.Float(), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("adjusted_p", sa.Float(), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("metadata", json_type(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.dataset_id"]),
        sa.PrimaryKeyConstraint("observation_id"),
    )


def downgrade() -> None:
    op.drop_table("omics_observations")
    op.drop_table("omics_associations")
    op.drop_table("natural_product_records")
    op.drop_index("idx_evidence_subject", table_name="evidence_items")
    op.drop_index("idx_evidence_source", table_name="evidence_items")
    op.drop_table("evidence_items")
    op.drop_index("idx_candidate_links_status", table_name="candidate_links")
    op.drop_index("idx_candidate_links_source", table_name="candidate_links")
    op.drop_table("candidate_links")
    op.drop_table("datasets")
    op.drop_index("idx_compounds_inchikey", table_name="compounds")
    op.drop_index("idx_compounds_canonical_name_lower", table_name="compounds")
    op.drop_table("compounds")
    op.drop_index("idx_taxa_canonical_name_lower", table_name="taxa")
    op.drop_table("taxa")
    op.drop_table("papers")
