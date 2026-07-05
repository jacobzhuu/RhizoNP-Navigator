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
    output = [str(item) for item in warnings]
    provenance = hit.get("provenance") or {}
    corpus_type = provenance.get("corpus_type")
    if hit.get("is_fixture"):
        output.append("Literature hit comes from a fixture/test corpus, not external evidence.")
    elif corpus_type:
        output.append(f"Literature corpus_type={corpus_type}.")
    output.append(
        "Retrieved passage is retrieval evidence only; co-occurrence does not imply production or causation."
    )
    return list(dict.fromkeys(output))


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
