from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from rhizonp.omics.csv_ingestion import (
    AssociationRecord,
    MetaboliteObservation,
    OwnDataBundle,
    TaxonObservation,
    load_own_data_bundle,
)
from rhizonp.omics.literature_bridge import OwnDataLiteratureRetriever
from rhizonp.omics.pipeline import (
    AssociationLinkResult,
    OwnDataPipelineOptions,
    run_own_data_bundle,
)
from rhizonp.writer.citation_validation import validate_citation_trace
from rhizonp.writer.evidence_adapter import literature_hits_to_evidence_items
from rhizonp.writer.faithfulness import evaluate_claim_faithfulness_diagnostics
from rhizonp.writer.models import EvidenceInput, WriterRequest
from rhizonp.writer.service import write_grounded_answer

RESULT_EVIDENCE_NAMESPACE = uuid.UUID("e71b42c7-5c08-4e7a-a11d-3f73da91c991")
_FEATURE_LIKE_PATTERN = re.compile(r"^(feature[_-]|m\d+$)", re.IGNORECASE)


@dataclass(frozen=True)
class ResultFindingInput:
    taxon: str
    metabolite: str
    association_direction: str
    effect_size: float
    p_value: float | None
    observation_method: str
    use_llm: bool = False
    retrieval_mode: str = "hybrid_rerank"
    top_k: int = 5
    max_queries: int = 3


def build_single_finding_bundle(finding: ResultFindingInput) -> OwnDataBundle:
    taxon_id = "taxon_input_1"
    metabolite_id = "metabolite_input_1"
    association_id = "association_input_1"
    feature_like = _looks_like_unconfirmed_feature(finding.metabolite)
    return OwnDataBundle(
        taxa=[
            TaxonObservation(
                observation_id=taxon_id,
                raw_label=finding.taxon.strip(),
                rank=_rank_from_observation_method(finding.observation_method),
                method=finding.observation_method.strip() or None,
                effect_size=finding.effect_size,
                adjusted_p=finding.p_value,
                metadata={"input_mode": "single_finding"},
            )
        ],
        metabolites=[
            MetaboliteObservation(
                observation_id=metabolite_id,
                raw_label=finding.metabolite.strip(),
                feature_id=finding.metabolite.strip() if feature_like else None,
                chemical_identification_tier=(
                    "C4_unknown_feature" if feature_like else "C2_or_name_level_annotation"
                ),
                method="LC-MS feature table",
                metadata={"input_mode": "single_finding"},
            )
        ],
        associations=[
            AssociationRecord(
                association_id=association_id,
                source_observation_id=taxon_id,
                target_observation_id=metabolite_id,
                source_raw_label=finding.taxon.strip(),
                target_raw_label=finding.metabolite.strip(),
                score=finding.effect_size,
                adjusted_p=finding.p_value,
                method="single_finding_interpretation",
                direction=finding.association_direction.strip() or None,
                metadata={
                    "correlation_not_causation": True,
                    "input_mode": "single_finding",
                },
            )
        ],
        provenance={
            "fixture": False,
            "dataset_name": "single_result_interpretation",
            "input_mode": "single_finding",
        },
    )


def interpret_single_finding(
    finding: ResultFindingInput,
    *,
    session: Session,
    natural_product_source: str = "auto",
    taxonomy_source: str = "auto",
    literature_retriever: OwnDataLiteratureRetriever | None = None,
) -> dict[str, Any]:
    bundle = build_single_finding_bundle(finding)
    return interpret_own_data_bundle(
        bundle,
        data_label="single_result_interpretation",
        session=session,
        use_llm=finding.use_llm,
        retrieval_mode=finding.retrieval_mode,
        top_k=finding.top_k,
        max_queries=finding.max_queries,
        natural_product_source=natural_product_source,
        taxonomy_source=taxonomy_source,
        literature_retriever=literature_retriever,
    )


def interpret_demo_results(
    *,
    session: Session,
    use_llm: bool = False,
    retrieval_mode: str = "hybrid_rerank",
    top_k: int = 5,
    max_queries: int = 3,
    natural_product_source: str = "auto",
    taxonomy_source: str = "auto",
    literature_retriever: OwnDataLiteratureRetriever | None = None,
) -> dict[str, Any]:
    bundle = load_own_data_bundle()
    return interpret_own_data_bundle(
        bundle,
        data_label="own_data_demo",
        session=session,
        use_llm=use_llm,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        max_queries=max_queries,
        natural_product_source=natural_product_source,
        taxonomy_source=taxonomy_source,
        literature_retriever=literature_retriever,
    )


def interpret_own_data_bundle(
    bundle: OwnDataBundle,
    *,
    data_label: str,
    session: Session,
    use_llm: bool = False,
    retrieval_mode: str = "hybrid_rerank",
    top_k: int = 5,
    max_queries: int = 3,
    natural_product_source: str = "auto",
    taxonomy_source: str = "auto",
    literature_retriever: OwnDataLiteratureRetriever | None = None,
) -> dict[str, Any]:
    pipeline = run_own_data_bundle(
        bundle,
        data_label=data_label,
        session=session,
        literature_retriever=literature_retriever,
        options=OwnDataPipelineOptions(
            enable_literature_retrieval=True,
            enable_grounded_writer=True,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            max_queries=max_queries,
            natural_product_source=natural_product_source,
            taxonomy_source=taxonomy_source,
        ),
    )
    interpretations = [
        _compose_association_interpretation(result, use_llm=use_llm)
        for result in pipeline.association_results
    ]
    return {
        "finding_count": len(interpretations),
        "interpretations": interpretations,
        "provenance": {
            **pipeline.provenance,
            "orchestrator": "rhizonp.omics.interpretation",
            "forced_literature_retrieval": True,
            "forced_grounded_writer": True,
            "writer_input": "literature_hits+natural_product_candidates+taxonomy_boundaries",
        },
    }


def _compose_association_interpretation(
    association: AssociationLinkResult,
    *,
    use_llm: bool,
) -> dict[str, Any]:
    candidate_rows = association.candidate_matrix.rows
    taxonomy = association.taxonomy_grading.to_dict() if association.taxonomy_grading else None
    literature = dict(association.literature_retrieval)
    literature_hits = list(literature.get("hits") or [])
    literature_evidence = literature_hits_to_evidence_items(literature_hits)
    candidate_evidence = _candidate_rows_to_evidence_items(
        association.association.association_id,
        association.taxon.raw_label,
        association.metabolite.raw_label,
        candidate_rows[:3],
    )
    evidence_items = [*candidate_evidence, *literature_evidence]
    taxonomy_warnings = _taxonomy_warnings(taxonomy, candidate_rows)
    limitations = list(
        dict.fromkeys(
            [
                *association.limitations,
                "结果解释将内部关联、结构化天然产物记录和文献召回整合为候选解释，不等同于因果证明。",
            ]
        )
    )
    request = WriterRequest(
        question=_writer_question(association),
        evidence_items=evidence_items,
        taxonomy_warnings=taxonomy_warnings,
        limitations=limitations,
    )
    answer = write_grounded_answer(request, use_llm=use_llm)
    citation_validation = validate_citation_trace(evidence_items, answer)
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    diagnostics = evaluate_claim_faithfulness_diagnostics(answer.claims, evidence_by_id)
    status = str(answer.status.value if hasattr(answer.status, "value") else answer.status)
    return {
        "association_id": association.association.association_id,
        "finding": _finding_payload(association),
        "status": status,
        "status_label": _status_label(status),
        "supported_interpretation": _supported_interpretation(association, status),
        "unsupported_interpretation": _unsupported_interpretation(association),
        "reasoning": _reasoning_steps(association, taxonomy, literature, candidate_rows),
        "literature_evidence": _literature_summary(literature),
        "natural_product_records": _natural_product_summary(candidate_rows),
        "next_steps": _validation_steps(association),
        "grounded_answer": answer.model_dump(mode="json"),
        "detailed_evidence": {
            "taxonomy_grading": taxonomy,
            "candidate_links": association.candidate_matrix.to_dict(),
            "literature_retrieval": literature,
            "pipeline_grounded_writer": association.grounded_writer,
            "combined_evidence_count": len(evidence_items),
            "candidate_evidence_count": len(candidate_evidence),
            "literature_evidence_count": len(literature_evidence),
            "writer_request": request.model_dump(mode="json"),
            "citation_validation": citation_validation.to_dict(),
            "faithfulness_diagnostics": diagnostics,
        },
    }


def _candidate_rows_to_evidence_items(
    association_id: str,
    query_taxon: str,
    metabolite_label: str,
    rows: Sequence[Any],
) -> list[EvidenceInput]:
    items: list[EvidenceInput] = []
    for row in rows:
        evidence_id = uuid.uuid5(
            RESULT_EVIDENCE_NAMESPACE,
            f"{association_id}:{row.rank}:{row.compound_name}:{row.producer_taxon}",
        )
        compound_context = (
            f"目标特征 {metabolite_label} 与记录化合物直接匹配"
            if row.compound_match
            else f"目标特征 {metabolite_label} 未与记录化合物直接匹配"
        )
        supporting_span = (
            f"Natural product candidate #{row.rank}: {row.compound_name} is recorded from "
            f"{row.producer_taxon}; query taxon is {query_taxon}; taxonomy distance is "
            f"{row.taxonomy_distance}; evidence tier is {row.evidence_tier}; {compound_context}."
        )
        direct = row.compound_match and row.evidence_tier in {"A", "B"}
        provenance = dict(row.provenance)
        provenance.update(
            {
                "source_type": "structured_natural_product_candidate",
                "candidate_rank": row.rank,
                "producer_taxon": row.producer_taxon,
                "compound_match": row.compound_match,
                "candidate_status": row.status,
                "association_id": association_id,
            }
        )
        items.append(
            EvidenceInput(
                evidence_id=evidence_id,
                claim_type="taxon_produces_compound",
                predicate="PRODUCES" if direct else "SUPPORTS",
                object_literal=row.compound_name,
                evidence_tier=row.evidence_tier,
                directness="direct" if direct else "indirect",
                confidence=0.85 if direct else 0.45,
                supporting_span=supporting_span,
                taxonomy_distance=row.taxonomy_distance,
                warnings=list(row.warnings),
                provenance=provenance,
            )
        )
    return items


def _finding_payload(association: AssociationLinkResult) -> dict[str, Any]:
    return {
        "taxon": association.taxon.raw_label,
        "metabolite": association.metabolite.raw_label,
        "association_direction": association.association.direction,
        "effect_size": association.association.score,
        "p_value": association.association.adjusted_p,
        "observation_method": association.taxon.method,
        "text": (
            f"{association.taxon.raw_label} 与 {association.metabolite.raw_label} "
            f"{_direction_phrase(association.association.direction)}，"
            f"effect = {association.association.score:g}"
            + (
                f", p = {association.association.adjusted_p:g}"
                if association.association.adjusted_p is not None
                else ""
            )
        ),
    }


def _literature_summary(literature: dict[str, Any]) -> dict[str, Any]:
    hits = list(literature.get("hits") or [])
    direct = 0
    indirect = 0
    items: list[dict[str, Any]] = []
    for hit in hits:
        grading = ((hit.get("taxonomy_grading") or {}).get("grading") or {})
        tier = str(grading.get("evidence_tier") or "D")
        is_direct = tier in {"A", "B"}
        direct += int(is_direct)
        indirect += int(not is_direct)
        items.append(
            {
                "title": hit.get("title"),
                "source": hit.get("journal") or hit.get("source_type"),
                "doi": hit.get("doi"),
                "pmid": hit.get("pmid"),
                "evidence_relation": "direct_or_close_taxonomy" if is_direct else "indirect_or_contextual",
                "taxonomy_distance": grading.get("taxonomy_distance"),
                "supporting_text": hit.get("supporting_text"),
            }
        )
    return {
        "status": literature.get("status"),
        "count": len(hits),
        "direct_count": direct,
        "indirect_count": indirect,
        "items": items,
    }


def _natural_product_summary(rows: Sequence[Any]) -> dict[str, Any]:
    direct_match: list[dict[str, Any]] = []
    same_species: list[dict[str, Any]] = []
    same_genus: list[dict[str, Any]] = []
    indirect_candidates: list[dict[str, Any]] = []
    for row in rows[:10]:
        payload = {
            "rank": row.rank,
            "compound_name": row.compound_name,
            "producer_taxon": row.producer_taxon,
            "taxonomy_distance": row.taxonomy_distance,
            "evidence_tier": row.evidence_tier,
            "status": row.status,
            "compound_match": row.compound_match,
            "score": row.score,
        }
        distance = row.taxonomy_distance.upper()
        if row.compound_match:
            direct_match.append(payload)
        elif "SPECIES" in distance:
            same_species.append(payload)
        elif "GENUS" in distance:
            same_genus.append(payload)
        else:
            indirect_candidates.append(payload)
    return {
        "direct_match": direct_match,
        "same_species": same_species,
        "same_genus": same_genus,
        "indirect_candidates": indirect_candidates,
    }


def _reasoning_steps(
    association: AssociationLinkResult,
    taxonomy: dict[str, Any] | None,
    literature: dict[str, Any],
    rows: Sequence[Any],
) -> list[str]:
    grading_distance = (taxonomy or {}).get("taxonomy_distance") or "unknown"
    tier = (taxonomy or {}).get("evidence_tier") or "D"
    hit_count = len(literature.get("hits") or [])
    candidate_count = len(rows)
    return [
        f"你的观测：{association.taxon.method or 'unknown method'} 观测到 {association.taxon.raw_label} 与 {association.metabolite.raw_label} 相关。",
        f"外部文献：Literature Bridge 返回 {hit_count} 条候选文献片段。",
        f"天然产物记录：NPAtlas/候选库返回 {candidate_count} 条候选记录。",
        f"分类学边界：最高候选的距离为 {grading_distance}，证据等级为 {tier}。",
        "因此：系统只能输出与证据等级一致的候选解释，并阻止把相关性或属级观测升级为直接生产结论。",
    ]


def _supported_interpretation(association: AssociationLinkResult, status: str) -> str:
    if status == "SUPPORTED":
        return (
            f"当前证据支持 {association.taxon.raw_label} 与 {association.metabolite.raw_label} "
            "相关解释中存在较强外部证据，可作为优先验证对象。"
        )
    if status == "PARTIALLY_SUPPORTED":
        return (
            f"当前结果支持 {association.taxon.raw_label} 的变化可能与 "
            f"{association.metabolite.raw_label} 所代表的代谢过程相关，但仍属于候选解释。"
        )
    return "当前证据不足，只能把该发现作为待扩展检索和实验验证的线索。"


def _unsupported_interpretation(association: AssociationLinkResult) -> str:
    return (
        f"不能证明样品中的 {association.taxon.raw_label} 直接产生 "
        f"{association.metabolite.raw_label}；也不能把相关性解释为因果或生物合成能力。"
    )


def _validation_steps(association: AssociationLinkResult) -> list[str]:
    steps = [
        "MS/MS annotation 或标准品比对确认代谢物身份。",
        "BGC analysis 检查相关生物合成基因簇。",
        "分离目标菌株并进行培养验证。",
        "targeted validation 验证候选代谢物与菌群变化是否可重复。",
    ]
    if _looks_like_unconfirmed_feature(association.metabolite.raw_label):
        steps.insert(0, "先将未知 LC-MS feature 提升为可信结构注释，再讨论具体化合物。")
    return steps


def _taxonomy_warnings(taxonomy: dict[str, Any] | None, rows: Sequence[Any]) -> list[str]:
    warnings = list((taxonomy or {}).get("warnings") or [])
    for row in rows[:3]:
        warnings.extend(row.warnings)
    return list(dict.fromkeys(str(item) for item in warnings if str(item).strip()))


def _writer_question(association: AssociationLinkResult) -> str:
    return (
        f"How should a {association.association.direction or 'reported'} association between "
        f"{association.taxon.raw_label} and {association.metabolite.raw_label} be interpreted "
        f"given taxonomy, natural product records, and retrieved literature evidence?"
    )


def _status_label(status: str) -> str:
    return {
        "SUPPORTED": "证据支持",
        "PARTIALLY_SUPPORTED": "部分支持",
        "INSUFFICIENT_EVIDENCE": "证据不足",
        "CONFLICTING_EVIDENCE": "证据冲突",
    }.get(status, status)


def _direction_phrase(direction: str | None) -> str:
    normalized = (direction or "").casefold()
    if normalized in {"positive", "up", "increased"}:
        return "显著正相关"
    if normalized in {"negative", "down", "decreased"}:
        return "显著负相关"
    return "存在关联"


def _rank_from_observation_method(method: str) -> str | None:
    lowered = method.casefold()
    if "genus" in lowered or "属" in method:
        return "genus"
    if "species" in lowered or "种" in method:
        return "species"
    if "strain" in lowered or "菌株" in method:
        return "strain"
    return None


def _looks_like_unconfirmed_feature(label: str) -> bool:
    stripped = label.strip()
    return bool(_FEATURE_LIKE_PATTERN.match(stripped))
