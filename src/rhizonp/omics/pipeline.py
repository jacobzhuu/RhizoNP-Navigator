from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT
from rhizonp.linking.candidate_engine import CandidateMatrix, link_natural_product_candidates
from rhizonp.omics.csv_ingestion import (
    DEFAULT_OWN_DATA_DIR,
    AssociationRecord,
    MetaboliteObservation,
    OwnDataBundle,
    TaxonObservation,
    load_own_data_bundle,
)
from rhizonp.taxonomy.grading import EvidenceGradingResult, grade_evidence


@dataclass(frozen=True)
class AssociationLinkResult:
    association: AssociationRecord
    taxon: TaxonObservation
    metabolite: MetaboliteObservation
    taxonomy_grading: EvidenceGradingResult | None
    candidate_matrix: CandidateMatrix
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "association_id": self.association.association_id,
            "source_raw_label": self.association.source_raw_label,
            "target_raw_label": self.association.target_raw_label,
            "score": self.association.score,
            "adjusted_p": self.association.adjusted_p,
            "method": self.association.method,
            "taxonomy_grading": (
                self.taxonomy_grading.to_dict() if self.taxonomy_grading is not None else None
            ),
            "candidate_links": self.candidate_matrix.to_dict(),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class OwnDataPipelineResult:
    bundle: OwnDataBundle
    association_results: list[AssociationLinkResult] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_provenance": dict(self.bundle.provenance),
            "pipeline_provenance": dict(self.provenance),
            "association_results": [result.to_dict() for result in self.association_results],
        }


def run_own_data_pipeline(
    data_dir: str | Path = DEFAULT_OWN_DATA_DIR,
) -> OwnDataPipelineResult:
    bundle = load_own_data_bundle(data_dir)
    taxa_by_id = {item.observation_id: item for item in bundle.taxa}
    metabolites_by_id = {item.observation_id: item for item in bundle.metabolites}

    results: list[AssociationLinkResult] = []
    for association in bundle.associations:
        taxon = taxa_by_id.get(association.source_observation_id)
        metabolite = metabolites_by_id.get(association.target_observation_id)
        if taxon is None or metabolite is None:
            continue

        limitations = [
            "Internal association is correlation-based and does not imply causation.",
        ]
        if metabolite.chemical_identification_tier and metabolite.chemical_identification_tier.startswith(
            "C4"
        ):
            limitations.append(
                "Metabolite feature is not structure-confirmed; compound links are name-level only."
            )

        candidate_matrix = link_natural_product_candidates(
            taxon.raw_label,
            metabolite_name=metabolite.raw_label,
            observation_method=taxon.method,
        )
        top_row = candidate_matrix.rows[0] if candidate_matrix.rows else None
        grading = None
        if top_row is not None:
            grading = grade_evidence(
                taxon.raw_label,
                top_row.producer_taxon,
                observation_method=taxon.method,
            )
            limitations.extend(grading.limitations)

        results.append(
            AssociationLinkResult(
                association=association,
                taxon=taxon,
                metabolite=metabolite,
                taxonomy_grading=grading,
                candidate_matrix=candidate_matrix,
                limitations=limitations,
            )
        )

    return OwnDataPipelineResult(
        bundle=bundle,
        association_results=results,
        provenance={
            "pipeline": "rhizonp.omics.pipeline",
            "data_dir": str(data_dir),
            "fixture": True,
        },
    )


def export_pipeline_json(result: OwnDataPipelineResult, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_candidate_matrix_csv(result: OwnDataPipelineResult, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "association_id",
        "source_raw_label",
        "target_raw_label",
        "association_score",
        "rank",
        "compound_name",
        "producer_taxon",
        "taxonomy_distance",
        "evidence_tier",
        "candidate_score",
        "status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for association_result in result.association_results:
            for row in association_result.candidate_matrix.rows:
                writer.writerow(
                    {
                        "association_id": association_result.association.association_id,
                        "source_raw_label": association_result.association.source_raw_label,
                        "target_raw_label": association_result.association.target_raw_label,
                        "association_score": association_result.association.score,
                        "rank": row.rank,
                        "compound_name": row.compound_name,
                        "producer_taxon": row.producer_taxon,
                        "taxonomy_distance": row.taxonomy_distance,
                        "evidence_tier": row.evidence_tier,
                        "candidate_score": row.score,
                        "status": row.status,
                    }
                )
    return path


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "own_data_demo"
