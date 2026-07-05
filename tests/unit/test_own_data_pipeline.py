from __future__ import annotations

from pathlib import Path

from rhizonp.config import PROJECT_ROOT
from rhizonp.omics.csv_ingestion import load_own_data_bundle
from rhizonp.omics.pipeline import (
    export_candidate_matrix_csv,
    export_pipeline_json,
    run_own_data_pipeline,
)


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
    assert genus_result.taxonomy_grading.evidence_tier.value in {"C", "D", "B", "A"}
