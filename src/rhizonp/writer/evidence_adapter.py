from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from rhizonp.omics.literature_bridge import LiteratureEvidenceHit
from rhizonp.writer.models import EvidenceInput

EVIDENCE_ID_NAMESPACE = uuid.UUID("a3f2c8e1-4b9d-5e6f-8a1c-2d3e4f5a6b7c")


def stable_evidence_id_for_chunk(chunk_id: str) -> uuid.UUID:
    return uuid.uuid5(EVIDENCE_ID_NAMESPACE, f"rhizonp:chunk:{chunk_id}")


def _coerce_hit(hit: LiteratureEvidenceHit | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(hit, LiteratureEvidenceHit):
        return hit.to_dict()
    return hit


def _extract_evidence_tier(hit: Mapping[str, Any]) -> str:
    grading_payload = hit.get("taxonomy_grading") or {}
    if grading_payload.get("status") != "graded":
        return "D"
    nested = grading_payload.get("grading") or {}
    tier = nested.get("evidence_tier")
    return str(tier) if tier else "D"


def _extract_taxonomy_distance(hit: Mapping[str, Any]) -> str | None:
    grading_payload = hit.get("taxonomy_grading") or {}
    nested = grading_payload.get("grading") or {}
    distance = nested.get("taxonomy_distance")
    return str(distance) if distance else None


def _extract_warnings(hit: Mapping[str, Any]) -> list[str]:
    grading_payload = hit.get("taxonomy_grading") or {}
    nested = grading_payload.get("grading") or {}
    warnings = nested.get("warnings") or []
    output = [_localize_warning(str(item)) for item in warnings]
    provenance = hit.get("provenance") or {}
    corpus_type = provenance.get("corpus_type")
    if hit.get("is_fixture"):
        output.append("该文献片段来自 fixture/test 语料，只能用于演示或回归测试。")
    elif corpus_type:
        output.append(f"文献语料来源类型：{corpus_type}。")
    output.append(
        "召回片段只能作为证据线索；文本共现不等同于生产或因果关系。"
    )
    return list(dict.fromkeys(output))


def _localize_warning(warning: str) -> str:
    warning_lower = warning.lower()
    if "genus-level" in warning_lower and "strain-level production" in warning_lower:
        return "属级或未解析的分类证据不能支持菌株水平生产主张。"
    if "same-genus evidence is candidate-level only" in warning_lower:
        return "同属证据只能作为候选线索，不能证明该样本生产目标化合物。"
    if "16s genus-level" in warning_lower and "strain-level production" in warning_lower:
        return "16S 属级观测不能提升为菌株水平生产结论。"
    return warning


def literature_hit_to_evidence_item(
    hit: LiteratureEvidenceHit | Mapping[str, Any],
) -> EvidenceInput:
    payload = _coerce_hit(hit)
    chunk_id = str(payload["chunk_id"])
    provenance = dict(payload.get("provenance") or {})
    provenance.update(
        {
            "chunk_id": chunk_id,
            "paper_id": str(payload.get("paper_id")),
            "pmid": payload.get("pmid"),
            "doi": payload.get("doi"),
            "source_url": payload.get("source_url"),
            "query_text": payload.get("query_text"),
            "retrieval_mode": payload.get("retrieval_mode"),
            "retrieval_score": payload.get("retrieval_score"),
            "corpus_type": provenance.get("corpus_type"),
            "corpus_id": provenance.get("corpus_id"),
            "is_fixture": bool(payload.get("is_fixture")),
            "source_type": payload.get("source_type"),
        }
    )
    return EvidenceInput(
        evidence_id=stable_evidence_id_for_chunk(chunk_id),
        claim_type="literature_retrieval_clue",
        predicate="MENTIONS",
        object_literal=payload.get("title"),
        evidence_tier=_extract_evidence_tier(payload),
        directness="indirect",
        confidence=0.3,
        supporting_span=str(payload.get("supporting_text") or "")[:2000] or None,
        taxonomy_distance=_extract_taxonomy_distance(payload),
        warnings=_extract_warnings(payload),
        provenance=provenance,
    )


def literature_hits_to_evidence_items(
    hits: Sequence[LiteratureEvidenceHit | Mapping[str, Any]],
) -> list[EvidenceInput]:
    return [literature_hit_to_evidence_item(hit) for hit in hits]
