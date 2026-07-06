from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from rhizonp.config import get_settings
from rhizonp.linking.candidate_engine import link_natural_product_candidates
from rhizonp.linking.np_adapter import NaturalProductSource
from rhizonp.literature.default_runtime import get_default_literature_runtime
from rhizonp.literature.retrieval import SearchFilters
from rhizonp.literature.service import LiteratureRetrievalService
from rhizonp.omics.literature_bridge import (
    LiteratureEvidenceHit,
    search_result_to_evidence_hit,
)
from rhizonp.query.llm_policy import resolve_use_llm
from rhizonp.writer.citation_validation import validate_citation_trace
from rhizonp.writer.faithfulness import evaluate_claim_faithfulness_diagnostics
from rhizonp.writer.models import EvidenceInput, WriterRequest
from rhizonp.writer.retrieval_writer import (
    RetrievalGroundedWriterResult,
    build_writer_request_from_literature_hits,
    write_grounded_answer_from_literature_hits,
)
from rhizonp.writer.service import write_grounded_answer

STRUCTURED_EVIDENCE_NAMESPACE = uuid.UUID("f032d8c3-f5d3-52a3-9194-f3b0d89239dd")

DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "Streptomyces": [
        "Streptomyces",
        "actinomycete",
        "actinobacteria",
        "secondary metabolites",
        "microbial natural products",
    ],
    "rhizosphere": [
        "rhizosphere",
        "plant-microbe interaction",
        "plant growth-promoting rhizobacteria",
        "PGPR",
    ],
    "root injury": [
        "root injury",
        "root wound",
        "plant stress response",
        "rhizosphere stress",
    ],
    "natural product": [
        "natural product",
        "secondary metabolite",
        "bioactive compound",
        "microbial metabolite",
    ],
    "LC-MS feature": [
        "LC-MS feature",
        "unknown metabolite feature",
        "metabolite annotation",
        "MS/MS validation",
    ],
    "A-503083 F": [
        "A-503083 F",
        "NPAtlas NPA000003",
        "Streptomyces sp. SANK 62799",
        "bacterial translocase I inhibitor",
    ],
}


@dataclass(frozen=True)
class PlannedQuery:
    query_text: str
    query_type: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_text": self.query_text,
            "query_type": self.query_type,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class QuestionPlan:
    original_question: str
    intent: str
    entities: dict[str, list[str]]
    synonym_expansions: dict[str, list[str]]
    planned_queries: list[PlannedQuery]
    warnings: list[str] = field(default_factory=list)
    planner_mode: str = "deterministic_domain_rules"

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_question": self.original_question,
            "intent": self.intent,
            "entities": self.entities,
            "synonym_expansions": self.synonym_expansions,
            "planned_queries": [query.to_dict() for query in self.planned_queries],
            "warnings": list(self.warnings),
            "planner_mode": self.planner_mode,
        }


@dataclass(frozen=True)
class AskPipelineResult:
    question_plan: QuestionPlan
    retrieval_hits: list[LiteratureEvidenceHit]
    writer_result: RetrievalGroundedWriterResult
    retrieval_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_plan": self.question_plan.to_dict(),
            "retrieval_mode": self.retrieval_mode,
            "retrieval_hits": [hit.to_dict() for hit in self.retrieval_hits],
            "answer": self.writer_result.answer.model_dump(mode="json"),
            "evidence_items": [
                item.model_dump(mode="json") for item in self.writer_result.evidence_items
            ],
            "citation_validation": self.writer_result.citation_validation.to_dict(),
            "faithfulness_diagnostics": list(self.writer_result.faithfulness_diagnostics),
            "provenance": self.writer_result.provenance,
        }


def build_question_plan(question: str) -> QuestionPlan:
    clean_question = " ".join(question.split())
    lower = clean_question.casefold()
    entities: dict[str, list[str]] = {
        "taxa": [],
        "compounds_or_features": [],
        "contexts": [],
    }
    synonym_expansions: dict[str, list[str]] = {}
    warnings: list[str] = []

    if "streptomyces sp. sank 62799" in lower:
        entities["taxa"].append("Streptomyces sp. SANK 62799")
        synonym_expansions["Streptomyces sp. SANK 62799"] = DOMAIN_SYNONYMS["Streptomyces"]
    elif "streptomyces hygroscopicus os-2" in lower:
        entities["taxa"].append("Streptomyces hygroscopicus OS-2")
        synonym_expansions["Streptomyces hygroscopicus OS-2"] = DOMAIN_SYNONYMS["Streptomyces"]
    elif "streptomyces" in lower:
        entities["taxa"].append("Streptomyces")
        synonym_expansions["Streptomyces"] = DOMAIN_SYNONYMS["Streptomyces"]
    if "rhizosphere" in lower or "根际" in clean_question:
        entities["contexts"].append("rhizosphere")
        synonym_expansions["rhizosphere"] = DOMAIN_SYNONYMS["rhizosphere"]
    if "root injury" in lower or "root wound" in lower or "损伤" in clean_question:
        entities["contexts"].append("root injury")
        synonym_expansions["root injury"] = DOMAIN_SYNONYMS["root injury"]
    if "feature" in lower or "lc-ms" in lower or "代谢特征" in clean_question:
        entities["compounds_or_features"].append("LC-MS feature")
        synonym_expansions["LC-MS feature"] = DOMAIN_SYNONYMS["LC-MS feature"]
        warnings.append("未知 LC-MS 特征不能直接当作已确认化合物。")
    if "a-503083 f" in lower:
        entities["compounds_or_features"].append("A-503083 F")
        synonym_expansions["A-503083 F"] = DOMAIN_SYNONYMS["A-503083 F"]
    if "natural product" in lower or "天然产物" in clean_question or "secondary metabolite" in lower:
        synonym_expansions["natural product"] = DOMAIN_SYNONYMS["natural product"]

    if any(token in lower for token in ("prove", "证明", "是否说明", "说明")):
        intent = "must_bound_claim"
        warnings.append("问题在询问较强结论，回答必须保留证据边界。")
    elif entities["taxa"] and entities["compounds_or_features"] and "LC-MS feature" not in entities["compounds_or_features"]:
        intent = "structured_taxon_compound_evidence"
    elif entities["taxa"] and ("natural product" in synonym_expansions or "天然产物" in clean_question):
        intent = "taxon_to_natural_product"
    elif entities["compounds_or_features"]:
        intent = "own_data_or_feature_to_literature"
    else:
        intent = "general_evidence_search"

    planned_queries: list[PlannedQuery] = [
        PlannedQuery(
            query_text=clean_question,
            query_type="original",
            rationale="保留用户原始问题作为主检索式。",
        )
    ]
    if entities["taxa"]:
        planned_queries.append(
            PlannedQuery(
                query_text=f"{entities['taxa'][0]} secondary metabolites natural products",
                query_type="taxon_np_expansion",
                rationale="把分类单元问题扩展到微生物天然产物和次级代谢物文献。",
            )
        )
    if entities["contexts"]:
        planned_queries.append(
            PlannedQuery(
                query_text=f"{' '.join(entities['contexts'])} plant microbe interaction rhizosphere",
                query_type="context_expansion",
                rationale="补充根际和植物-微生物互作语境证据。",
            )
        )
    if entities["compounds_or_features"]:
        taxon = entities["taxa"][0] if entities["taxa"] else ""
        planned_queries.append(
            PlannedQuery(
                query_text=f"{taxon} metabolite annotation secondary metabolites".strip(),
                query_type="feature_safe_expansion",
                rationale="避免把未知特征当作已确认化合物，改用代谢物注释相关语境检索。",
            )
        )

    deduped_queries: list[PlannedQuery] = []
    seen: set[str] = set()
    for planned in planned_queries:
        key = planned.query_text.casefold()
        if key and key not in seen:
            seen.add(key)
            deduped_queries.append(planned)

    return QuestionPlan(
        original_question=clean_question,
        intent=intent,
        entities={key: list(dict.fromkeys(values)) for key, values in entities.items()},
        synonym_expansions=synonym_expansions,
        planned_queries=deduped_queries,
        warnings=list(dict.fromkeys(warnings)),
    )


def _dedupe_hits(hits: list[LiteratureEvidenceHit], *, top_k: int) -> list[LiteratureEvidenceHit]:
    deduped: list[LiteratureEvidenceHit] = []
    seen_chunks: set[str] = set()
    for hit in hits:
        if hit.chunk_id in seen_chunks:
            continue
        seen_chunks.add(hit.chunk_id)
        deduped.append(hit)
        if len(deduped) >= top_k:
            break
    return deduped


def _stable_structured_evidence_id(*, source: str, record_id: str, query_taxon: str, compound: str) -> uuid.UUID:
    return uuid.uuid5(
        STRUCTURED_EVIDENCE_NAMESPACE,
        f"{source}:{record_id}:{query_taxon}:{compound}",
    )


def _structured_np_evidence_items(plan: QuestionPlan) -> list[EvidenceInput]:
    taxa = plan.entities.get("taxa") or []
    compounds = [
        value
        for value in plan.entities.get("compounds_or_features", [])
        if value != "LC-MS feature"
    ]
    if not taxa or not compounds:
        return []

    matrix = link_natural_product_candidates(
        taxa[0],
        metabolite_name=compounds[0],
        record_source=NaturalProductSource.NPATLAS_BOUNDED,
    )
    items: list[EvidenceInput] = []
    for row in matrix.rows:
        if not row.compound_match:
            continue
        provenance = dict(row.provenance)
        origin_reference = provenance.get("origin_reference") or {}
        source_url = provenance.get("source_url")
        external_id = str(provenance.get("external_record_id") or provenance.get("npaid") or row.compound_name)
        reference_bits = [
            str(origin_reference.get("title") or "").strip(),
            str(origin_reference.get("journal") or "").strip(),
            str(origin_reference.get("year") or "").strip(),
        ]
        reference_text = ", ".join(bit for bit in reference_bits if bit)
        supporting_span = (
            f"NPAtlas bounded record {external_id} lists {row.compound_name} as a natural product "
            f"from {row.producer_taxon}."
        )
        if reference_text:
            supporting_span += f" Origin reference: {reference_text}."
        if source_url:
            supporting_span += f" Source: {source_url}."

        provenance.update(
            {
                "source_type": "structured_natural_product_database",
                "source_database": provenance.get("source_database") or "npatlas",
                "doi": origin_reference.get("doi"),
                "pmid": str(origin_reference.get("pmid")) if origin_reference.get("pmid") else None,
                "source_url": source_url,
                "real_bounded_npatlas": True,
                "not_synthetic_fixture": True,
            }
        )
        items.append(
            EvidenceInput(
                evidence_id=_stable_structured_evidence_id(
                    source="npatlas",
                    record_id=external_id,
                    query_taxon=taxa[0],
                    compound=row.compound_name,
                ),
                claim_type="taxon_produces_compound",
                predicate="PRODUCES",
                object_literal=row.compound_name,
                evidence_tier=row.evidence_tier,
                directness="direct" if row.evidence_tier in {"A", "B"} else "indirect",
                confidence=0.9 if row.evidence_tier == "A" else 0.75,
                supporting_span=supporting_span,
                taxonomy_distance=row.taxonomy_distance,
                warnings=list(row.warnings),
                provenance=provenance,
            )
        )
        break
    return items


def _write_answer_from_combined_evidence(
    question: str,
    hits: list[LiteratureEvidenceHit],
    structured_evidence: list[EvidenceInput],
    *,
    limitations: list[str],
    taxonomy_warnings: list[str],
    retrieval_status: str,
    use_llm: bool,
) -> RetrievalGroundedWriterResult:
    if not structured_evidence:
        return write_grounded_answer_from_literature_hits(
            question,
            hits,
            limitations=limitations,
            taxonomy_warnings=taxonomy_warnings,
            retrieval_status=retrieval_status,
            use_llm=use_llm,
        )

    literature_request = build_writer_request_from_literature_hits(
        question,
        hits,
        limitations=limitations,
        taxonomy_warnings=taxonomy_warnings,
    )
    request = WriterRequest(
        question=question,
        evidence_items=[*structured_evidence, *literature_request.evidence_items],
        taxonomy_warnings=list(dict.fromkeys(taxonomy_warnings)),
        limitations=list(
            dict.fromkeys(
                [
                    *literature_request.limitations,
                    "结构化 NPAtlas bounded snapshot 记录可作为真实天然产物数据库证据；仍需查看原始来源文献确认实验细节。",
                ]
            )
        ),
    )
    answer = write_grounded_answer(request, use_llm=use_llm)
    validation = validate_citation_trace(request.evidence_items, answer)
    evidence_by_id = {item.evidence_id: item for item in request.evidence_items}
    diagnostics = evaluate_claim_faithfulness_diagnostics(answer.claims, evidence_by_id)
    return RetrievalGroundedWriterResult(
        answer=answer,
        evidence_items=request.evidence_items,
        citation_validation=validation,
        faithfulness_diagnostics=diagnostics,
        retrieval_status=retrieval_status,
        provenance={
            "writer_input": "literature_retrieval+structured_npatlas",
            "hit_count": len(hits),
            "structured_evidence_count": len(structured_evidence),
            "structured_source": "npatlas_bounded",
            "retrieval_status": retrieval_status,
        },
    )


def run_ask_pipeline(
    session: Session,
    question: str,
    *,
    retrieval_mode: str = "hybrid_rerank",
    top_k: int = 5,
    max_queries: int = 3,
    use_llm: bool | None = None,
    retrieval_service: LiteratureRetrievalService | None = None,
) -> AskPipelineResult:
    service = retrieval_service or LiteratureRetrievalService(get_default_literature_runtime())
    resolved_use_llm = resolve_use_llm(use_llm, get_settings())
    plan = build_question_plan(question)
    hits: list[LiteratureEvidenceHit] = []
    for query_index, planned in enumerate(plan.planned_queries[:max_queries], start=1):
        results = service.search(
            session,
            planned.query_text,
            top_k=top_k,
            filters=SearchFilters(),
            retrieval_mode=retrieval_mode,
        )
        for result in results:
            hit = search_result_to_evidence_hit(
                session,
                result,
                query_text=planned.query_text,
                query_index=query_index,
                retrieval_mode=retrieval_mode,
                query_taxon=(plan.entities.get("taxa") or [question])[0],
                observation_method="unified_question",
            )
            hits.append(hit)

    deduped_hits = _dedupe_hits(hits, top_k=top_k)
    structured_evidence = _structured_np_evidence_items(plan)
    writer_result = _write_answer_from_combined_evidence(
        question,
        deduped_hits,
        structured_evidence,
        limitations=[
            "统一问答流程将召回文献片段作为候选证据，而不是最终事实库。",
            "RAG 合成不能替代实验验证。",
        ],
        taxonomy_warnings=plan.warnings,
        retrieval_status="RETRIEVED" if deduped_hits else "NO_RESULTS",
        use_llm=resolved_use_llm,
    )
    return AskPipelineResult(
        question_plan=plan,
        retrieval_hits=deduped_hits,
        writer_result=writer_result,
        retrieval_mode=retrieval_mode,
    )
