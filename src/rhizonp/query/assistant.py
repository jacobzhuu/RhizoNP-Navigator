from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from rhizonp.literature.retrieval import SearchFilters, search_paper_chunks
from rhizonp.omics.literature_bridge import (
    LiteratureEvidenceHit,
    search_result_to_evidence_hit,
)
from rhizonp.writer.retrieval_writer import (
    RetrievalGroundedWriterResult,
    write_grounded_answer_from_literature_hits,
)

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

    if "streptomyces" in lower:
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
    if "natural product" in lower or "天然产物" in clean_question or "secondary metabolite" in lower:
        synonym_expansions["natural product"] = DOMAIN_SYNONYMS["natural product"]

    if any(token in lower for token in ("prove", "证明", "是否说明", "说明")):
        intent = "must_bound_claim"
        warnings.append("问题在询问较强结论，回答必须保留证据边界。")
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


def run_ask_pipeline(
    session: Session,
    question: str,
    *,
    retrieval_mode: str = "hybrid_rerank",
    top_k: int = 5,
    max_queries: int = 3,
    use_llm: bool = False,
) -> AskPipelineResult:
    plan = build_question_plan(question)
    hits: list[LiteratureEvidenceHit] = []
    for query_index, planned in enumerate(plan.planned_queries[:max_queries], start=1):
        results = search_paper_chunks(
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
    writer_result = write_grounded_answer_from_literature_hits(
        question,
        deduped_hits,
        limitations=[
            "统一问答流程将召回文献片段作为候选证据，而不是最终事实库。",
            "RAG 合成不能替代实验验证。",
        ],
        taxonomy_warnings=plan.warnings,
        retrieval_status="RETRIEVED" if deduped_hits else "NO_RESULTS",
        use_llm=use_llm,
    )
    return AskPipelineResult(
        question_plan=plan,
        retrieval_hits=deduped_hits,
        writer_result=writer_result,
        retrieval_mode=retrieval_mode,
    )
