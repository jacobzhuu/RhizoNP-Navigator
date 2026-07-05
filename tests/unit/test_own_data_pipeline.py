from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base, OmicsAssociation, OmicsObservation
from rhizonp.omics.csv_ingestion import load_own_data_bundle
from rhizonp.omics.pipeline import (
    OwnDataPipelineOptions,
    export_candidate_matrix_csv,
    export_pipeline_json,
    run_own_data_pipeline,
)
from rhizonp.storage.postgres import create_session_factory
from rhizonp.taxonomy.models import TaxonomyDistance


def _sqlite_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return create_session_factory(engine)()


def test_load_own_data_csv_bundle() -> None:
    data_dir = PROJECT_ROOT / "data" / "fixtures" / "own_data_demo"
    bundle = load_own_data_bundle(data_dir)
    assert len(bundle.taxa) == 2
    assert len(bundle.metabolites) == 2
    assert len(bundle.associations) == 2
    assert bundle.provenance["fixture"] is True


def test_pipeline_links_associations_to_candidates() -> None:
    result = run_own_data_pipeline(PROJECT_ROOT / "data" / "fixtures" / "own_data_demo")
    assert len(result.association_results) == 2
    first = result.association_results[0]
    assert first.association.source_raw_label == "Streptomyces"
    assert first.candidate_matrix.rows
    assert first.limitations
    assert first.literature_retrieval["status"] == "DISABLED"


def test_pipeline_exports_json_and_csv(tmp_path: Path) -> None:
    result = run_own_data_pipeline(PROJECT_ROOT / "data" / "fixtures" / "own_data_demo")
    json_path = export_pipeline_json(result, tmp_path / "pipeline_result.json")
    csv_path = export_candidate_matrix_csv(result, tmp_path / "candidate_matrix.csv")
    assert json_path.exists()
    assert csv_path.exists()
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "association_id" in csv_text
    assert "Streptomyces" in csv_text


def test_genus_16s_association_carries_taxonomy_warnings() -> None:
    result = run_own_data_pipeline(PROJECT_ROOT / "data" / "fixtures" / "own_data_demo")
    genus_result = next(
        item for item in result.association_results if item.taxon.raw_label == "Streptomyces"
    )
    assert genus_result.taxonomy_grading is not None
    assert genus_result.taxonomy_grading.taxonomy_distance == TaxonomyDistance.SAME_GENUS
    assert genus_result.taxonomy_grading.evidence_tier.value == "C"
    assert genus_result.taxonomy_grading.max_supported_claim == "genus_level_candidate"
    feature_row = genus_result.candidate_matrix.rows[0]
    assert feature_row.compound_match is False
    assert feature_row.status == "PARTIALLY_SUPPORTED"


def test_pipeline_persists_bundle_to_database_when_enabled() -> None:
    data_dir = PROJECT_ROOT / "data" / "fixtures" / "own_data_demo"
    session = _sqlite_session()
    try:
        result = run_own_data_pipeline(
            data_dir,
            session=session,
            options=OwnDataPipelineOptions(persist_to_database=True),
        )
        assert result.provenance["database_persistence"] is not None
        assert result.provenance["database_persistence"]["association_count"] == 2
        assert result.provenance["database_persistence"]["observation_count"] == 4

        associations = list(session.scalars(select(OmicsAssociation)))
        observations = list(session.scalars(select(OmicsObservation)))
        assert len(associations) == 2
        assert len(observations) == 4
        assert all(item.association_metadata.get("correlation_not_causation") for item in associations)
        assert any(item.source_raw_label == "Streptomyces" for item in associations)
    finally:
        session.close()
