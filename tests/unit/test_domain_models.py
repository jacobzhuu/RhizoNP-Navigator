import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rhizonp.domain.models import (
    Base,
    CandidateLink,
    Compound,
    Dataset,
    EvidenceItem,
    NaturalProductRecord,
    OmicsAssociation,
    OmicsObservation,
    Paper,
    Taxon,
)


def test_phase_1_metadata_contains_required_tables() -> None:
    expected_tables = {
        "papers",
        "taxa",
        "compounds",
        "natural_product_records",
        "datasets",
        "omics_observations",
        "omics_associations",
        "evidence_items",
        "candidate_links",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_phase_1_metadata_contains_required_indexes_and_constraints() -> None:
    index_names = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    np_constraints = {
        constraint.name
        for constraint in Base.metadata.tables["natural_product_records"].constraints
    }

    assert "idx_taxa_canonical_name_lower" in index_names
    assert "idx_compounds_canonical_name_lower" in index_names
    assert "idx_evidence_subject" in index_names
    assert "idx_candidate_links_source" in index_names
    assert "uq_np_source_record" in np_constraints


def test_phase_1_schema_can_create_all_tables_in_sqlite() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)

    assert set(Base.metadata.tables).issuperset(
        {
            Paper.__tablename__,
            Taxon.__tablename__,
            Compound.__tablename__,
            NaturalProductRecord.__tablename__,
            Dataset.__tablename__,
            OmicsObservation.__tablename__,
            OmicsAssociation.__tablename__,
            EvidenceItem.__tablename__,
            CandidateLink.__tablename__,
        }
    )


def test_model_defaults_are_not_shared_between_instances() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    paper_a = Paper(title="A")
    paper_b = Paper(title="B")

    with Session(engine) as session:
        session.add_all([paper_a, paper_b])
        session.flush()
        paper_a.provenance["source"] = "fixture"

    assert paper_b.provenance == {}
    assert isinstance(paper_a.paper_id, uuid.UUID)
