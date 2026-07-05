from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

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
from rhizonp.omics.literature_bridge import (
    LiteratureRetrievalStatus,
    OwnDataLiteratureRetriever,
    retrieve_literature_for_association,
)
from rhizonp.omics.query_builder import build_query_context
from rhizonp.taxonomy.grading import EvidenceGradingResult, grade_evidence


@dataclass(frozen=True)
class OwnDataPipelineOptions:
    enable_literature_retrieval: bool = False
    retrieval_mode: str = "hybrid_rerank"
    top_k: int = 5
    max_queries: int = 3
    corpus_id: str | None = None
    corpus_type: str | None = None


@dataclass(frozen=True)
class AssociationLinkResult:
    association: AssociationRecord
    taxon: TaxonObservation
    metabolite: MetaboliteObservation
    literature_retrieval: dict[str, Any]
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
            "literature_retrieval": dict(self.literature_retrieval),
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


def _append_literature_limitations(
    limitations: list[str],
    literature_retrieval: dict[str, Any],
) -> None:
    status = literature_retrieval.get("status")
    if status == LiteratureRetrievalStatus.DISABLED.value:
        limitations.append(
            "Literature retrieval was not executed for this run (disabled)."
        )
    elif status == LiteratureRetrievalStatus.RETRIEVAL_UNAVAILABLE.value:
        reason = literature_retrieval.get("reason") or "Literature retrieval unavailable."
        limitations.append(reason)
    elif status == LiteratureRetrievalStatus.FIXTURE_TEST_ONLY.value:
        limitations.append(
            "Literature hits come from an explicit fixture/test corpus and are not external evidence."
        )
    elif status == LiteratureRetrievalStatus.RETRIEVED.value:
        limitations.append(
            "Retrieved literature passages are retrieval evidence only; "
            "co-occurrence in text does not imply biochemical production or causation."
        )
        for hit in literature_retrieval.get("hits", []):
            grading = hit.get("taxonomy_grading") or {}
            nested = grading.get("grading") or {}
            for warning in nested.get("warnings", []):
                limitations.append(str(warning))
    elif status == LiteratureRetrievalStatus.NO_RESULTS.value:
        limitations.append("No literature chunks matched the generated association queries.")


def run_own_data_pipeline(
    data_dir: str | Path = DEFAULT_OWN_DATA_DIR,
    *,
    session: Session | None = None,
    options: OwnDataPipelineOptions | None = None,
    literature_retriever: OwnDataLiteratureRetriever | None = None,
) -> OwnDataPipelineResult:
    resolved_options = options or OwnDataPipelineOptions()
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

        query_context = build_query_context(
            taxon,
            metabolite,
            association_score=association.score,
        )
        literature_retrieval = retrieve_literature_for_association(
            query_context,
            query_taxon=taxon.raw_label,
            observation_method=taxon.method,
            enabled=resolved_options.enable_literature_retrieval,
            session=session,
            retriever=literature_retriever,
            retrieval_mode=resolved_options.retrieval_mode,
            top_k=resolved_options.top_k,
            max_queries=resolved_options.max_queries,
            corpus_id=resolved_options.corpus_id,
            corpus_type=resolved_options.corpus_type,
        ).to_dict()
        _append_literature_limitations(limitations, literature_retrieval)

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
                literature_retrieval=literature_retrieval,
                taxonomy_grading=grading,
                candidate_matrix=candidate_matrix,
                limitations=list(dict.fromkeys(limitations)),
            )
        )

    return OwnDataPipelineResult(
        bundle=bundle,
        association_results=results,
        provenance={
            "pipeline": "rhizonp.omics.pipeline",
            "data_dir": str(data_dir),
            "fixture": True,
            "literature_retrieval_enabled": resolved_options.enable_literature_retrieval,
            "literature_retrieval_mode": resolved_options.retrieval_mode,
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
        "literature_status",
        "literature_hit_count",
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
            literature = association_result.literature_retrieval
            for row in association_result.candidate_matrix.rows:
                writer.writerow(
                    {
                        "association_id": association_result.association.association_id,
                        "source_raw_label": association_result.association.source_raw_label,
                        "target_raw_label": association_result.association.target_raw_label,
                        "association_score": association_result.association.score,
                        "literature_status": literature.get("status"),
                        "literature_hit_count": len(literature.get("hits", [])),
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
