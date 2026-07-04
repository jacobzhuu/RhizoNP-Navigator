from sqlalchemy import create_engine

from rhizonp.domain.models import Base
from rhizonp.ingestion.fixtures import DEFAULT_PHASE1_FIXTURE_PATH, load_phase1_demo_fixture
from rhizonp.storage.postgres import create_session_factory, session_scope
from rhizonp.storage.repositories import (
    CandidateLinkRepository,
    CompoundRepository,
    DatasetRepository,
    EvidenceRepository,
    NaturalProductRecordRepository,
    TaxonRepository,
)


def test_phase1_demo_fixture_loads_and_preserves_scientific_boundaries() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        summary = load_phase1_demo_fixture(session, DEFAULT_PHASE1_FIXTURE_PATH)

    assert summary.papers == 1
    assert summary.taxa == 1
    assert summary.compounds == 1
    assert summary.natural_product_records == 1
    assert summary.datasets == 1
    assert summary.omics_observations == 2
    assert summary.omics_associations == 1
    assert summary.evidence_items == 1
    assert summary.candidate_links == 1

    with session_scope(session_factory) as session:
        taxon = TaxonRepository(session).find_by_canonical_name("streptomyces")
        compound = CompoundRepository(session).find_by_canonical_name("fixturepolyketide-a")
        dataset = DatasetRepository(session).find_by_name("Synthetic root injury own-omics demo")

        assert taxon is not None
        assert taxon.rank == "genus"
        assert compound is not None
        assert compound.structure_status == "unknown"
        assert dataset is not None
        assert dataset.provenance["not_real_experiment"] is True

        np_record = NaturalProductRecordRepository(session).find_by_source_record(
            source_database="synthetic_fixture",
            external_record_id="NP_FIXTURE_001",
        )
        assert np_record is not None
        assert np_record.provenance["not_real_database_record"] is True

        evidence = EvidenceRepository(session).list_for_subject(
            subject_entity_type="taxon",
            subject_entity_id=taxon.taxon_id,
        )
        candidates = CandidateLinkRepository(session).list_by_status("PARTIALLY_SUPPORTED")

        assert len(evidence) == 1
        assert evidence[0].evidence_tier == "same_genus"
        assert evidence[0].directness == "indirect"
        assert len(candidates) == 1
        assert candidates[0].taxonomy_distance == "same_genus"
        assert "genus-level" in candidates[0].rationale["limitation"]
