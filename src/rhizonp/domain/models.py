from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON as SQLAlchemyJSON
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSON_TYPE = SQLAlchemyJSON().with_variant(postgresql.JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Paper(TimestampMixin, Base):
    __tablename__ = "papers"

    paper_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doi: Mapped[str | None] = mapped_column(Text, unique=True)
    pmid: Mapped[str | None] = mapped_column(Text)
    pmcid: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    journal: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    natural_product_records: Mapped[list[NaturalProductRecord]] = relationship(
        back_populates="reference_paper"
    )


class Taxon(TimestampMixin, Base):
    __tablename__ = "taxa"

    taxon_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[str | None] = mapped_column(String(64))
    strain: Mapped[str | None] = mapped_column(Text)
    species: Mapped[str | None] = mapped_column(Text)
    genus: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    external_ids: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    normalization_status: Mapped[str] = mapped_column(String(64), default="unresolved", nullable=False)

    natural_product_records: Mapped[list[NaturalProductRecord]] = relationship(
        back_populates="producer_taxon"
    )


class Compound(TimestampMixin, Base):
    __tablename__ = "compounds"

    compound_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    smiles: Mapped[str | None] = mapped_column(Text)
    inchikey: Mapped[str | None] = mapped_column(Text)
    formula: Mapped[str | None] = mapped_column(Text)
    compound_class: Mapped[str | None] = mapped_column(Text)
    structure_status: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    external_ids: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    natural_product_records: Mapped[list[NaturalProductRecord]] = relationship(
        back_populates="compound"
    )


class NaturalProductRecord(Base):
    __tablename__ = "natural_product_records"
    __table_args__ = (
        UniqueConstraint("source_database", "external_record_id", name="uq_np_source_record"),
    )

    np_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    compound_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compounds.compound_id"), nullable=False)
    producer_taxon_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxa.taxon_id"))
    source_database: Mapped[str] = mapped_column(Text, nullable=False)
    external_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    bioactivity_summary: Mapped[str | None] = mapped_column(Text)
    reference_paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.paper_id"))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    compound: Mapped[Compound] = relationship(back_populates="natural_product_records")
    producer_taxon: Mapped[Taxon | None] = relationship(back_populates="natural_product_records")
    reference_paper: Mapped[Paper | None] = relationship(back_populates="natural_product_records")


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[str] = mapped_column(String(128), nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    observations: Mapped[list[OmicsObservation]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    associations: Mapped[list[OmicsAssociation]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class OmicsObservation(Base):
    __tablename__ = "omics_observations"

    observation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.dataset_id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    raw_label: Mapped[str] = mapped_column(Text, nullable=False)
    treatment: Mapped[str | None] = mapped_column(Text)
    timepoint: Mapped[str | None] = mapped_column(Text)
    layer: Mapped[str | None] = mapped_column(Text)
    effect_size: Mapped[float | None] = mapped_column(Float)
    p_value: Mapped[float | None] = mapped_column(Float)
    adjusted_p: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    observation_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON_TYPE,
        default=dict,
        nullable=False,
    )

    dataset: Mapped[Dataset] = relationship(back_populates="observations")


class OmicsAssociation(Base):
    __tablename__ = "omics_associations"

    association_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.dataset_id"), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_raw_label: Mapped[str] = mapped_column(Text, nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    target_raw_label: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    adjusted_p: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str | None] = mapped_column(String(64))
    treatment: Mapped[str | None] = mapped_column(Text)
    timepoint: Mapped[str | None] = mapped_column(Text)
    association_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON_TYPE,
        default=dict,
        nullable=False,
    )

    dataset: Mapped[Dataset] = relationship(back_populates="associations")


class EvidenceItem(TimestampMixin, Base):
    __tablename__ = "evidence_items"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    claim_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    predicate: Mapped[str] = mapped_column(String(128), nullable=False)
    object_entity_type: Mapped[str | None] = mapped_column(String(64))
    object_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    object_literal: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    evidence_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    directness: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    supporting_span: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)


class CandidateLink(TimestampMixin, Base):
    __tablename__ = "candidate_links"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    relation: Mapped[str] = mapped_column(String(128), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    internal_evidence_score: Mapped[float | None] = mapped_column(Float)
    external_evidence_score: Mapped[float | None] = mapped_column(Float)
    taxonomy_distance: Mapped[str | None] = mapped_column(String(64))
    evidence_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)


Index("idx_taxa_canonical_name_lower", func.lower(Taxon.canonical_name))
Index("idx_compounds_canonical_name_lower", func.lower(Compound.canonical_name))
Index("idx_compounds_inchikey", Compound.inchikey)
Index("idx_evidence_subject", EvidenceItem.subject_entity_type, EvidenceItem.subject_entity_id)
Index("idx_evidence_source", EvidenceItem.source_type, EvidenceItem.source_id)
Index("idx_candidate_links_source", CandidateLink.source_entity_type, CandidateLink.source_entity_id)
Index("idx_candidate_links_status", CandidateLink.status)
