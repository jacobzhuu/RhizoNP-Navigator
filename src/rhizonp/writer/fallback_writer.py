from __future__ import annotations

from collections.abc import Sequence

from rhizonp.taxonomy.policy import tier_allows_species_claim, tier_allows_strain_claim
from rhizonp.writer.models import (
    AnswerStatus,
    Claim,
    EvidenceInput,
    GroundedAnswer,
    WriterRequest,
)

_CAUSALITY_LIMITATION = "相关性或共现并不等同于生物化学意义上的生产或因果关系。"


def _tier_rank(tier: str) -> int:
    normalized = tier.upper().replace("TIER ", "")
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(normalized, 0)


def _detect_conflicts(evidence_items: Sequence[EvidenceInput]) -> bool:
    supports: set[str] = set()
    refutes: set[str] = set()
    for item in evidence_items:
        predicate = item.predicate.upper()
        key = item.object_literal or item.claim_type
        if predicate in {"PRODUCES", "SUPPORTS"}:
            supports.add(key)
        if predicate in {"DOES_NOT_PRODUCE", "REFUTES", "NEGATES"}:
            refutes.add(key)
    return bool(supports & refutes)


def _strongest_tier(evidence_items: Sequence[EvidenceInput]) -> str:
    if not evidence_items:
        return "D"
    return max((item.evidence_tier for item in evidence_items), key=_tier_rank)


def _build_claims(
    request: WriterRequest,
    *,
    allow_strain_claim: bool,
    allow_species_claim: bool,
) -> list[Claim]:
    claims: list[Claim] = []
    merged_claim_refs: dict[tuple[str, str], list] = {}
    for item in request.evidence_items:
        if item.predicate.upper() in {"DOES_NOT_PRODUCE", "REFUTES", "NEGATES"}:
            claims.append(
                Claim(
                    text=(
                        f"冲突证据表明，针对 {item.object_literal or '目标实体'} 的"
                        f"相关关系可能不成立。"
                    ),
                    evidence_refs=[item.evidence_id],
                    claim_level="conflict",
                )
            )
            continue

        if not allow_strain_claim and "strain" in item.claim_type.lower():
            continue

        claim_text = item.supporting_span or (
            f"证据（{item.evidence_tier}）以 {item.directness} 直接性"
            f"支持 {item.claim_type.replace('_', ' ')}。"
        )
        if not allow_strain_claim and tier_allows_strain_claim(item.evidence_tier) is False:
            claim_text = (
                f"候选级证据（{item.evidence_tier}）与 "
                f"{item.object_literal or '相关实体'} 相关；不支持菌株水平生产主张。"
            )
        elif not allow_species_claim:
            claim_text = (
                f"针对 {item.object_literal or '目标实体'} 仅有较弱分类学证据"
                f"（{item.evidence_tier}）。"
            )

        claim_level = "descriptive" if allow_species_claim else "candidate"
        key = (claim_text, claim_level)
        merged_claim_refs.setdefault(key, []).append(item.evidence_id)
    claims.extend(
        Claim(
            text=text,
            evidence_refs=list(dict.fromkeys(refs)),
            claim_level=claim_level,
        )
        for (text, claim_level), refs in merged_claim_refs.items()
    )
    return claims


def write_fallback_answer(request: WriterRequest) -> GroundedAnswer:
    if not request.evidence_items:
        return GroundedAnswer(
            status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            answer="现有证据不足以保守地回答该问题。",
            claims=[],
            evidence_refs=[],
            limitations=list(request.limitations) + ["未提供任何证据条目。"],
            suggested_validations=[
                "请扩展文献检索或补充结构化数据库记录。",
            ],
            writer_mode="fallback",
            provenance={"writer": "rhizonp.writer.fallback_writer"},
        )

    if _detect_conflicts(request.evidence_items):
        refs = [item.evidence_id for item in request.evidence_items]
        return GroundedAnswer(
            status=AnswerStatus.CONFLICTING_EVIDENCE,
            answer="发现相互冲突的证据，系统无法选定单一支持性结论。",
            claims=_build_claims(request, allow_strain_claim=False, allow_species_claim=False),
            evidence_refs=refs,
            limitations=list(request.limitations) + list(request.taxonomy_warnings),
            suggested_validations=["请查阅原始来源并协调冲突记录。"],
            writer_mode="fallback",
            provenance={"writer": "rhizonp.writer.fallback_writer"},
        )

    strongest_tier = _strongest_tier(request.evidence_items)
    allow_strain = tier_allows_strain_claim(strongest_tier) and not request.taxonomy_warnings
    allow_species = tier_allows_species_claim(strongest_tier)
    claims = _build_claims(
        request,
        allow_strain_claim=allow_strain,
        allow_species_claim=allow_species,
    )
    refs = [item.evidence_id for item in request.evidence_items]

    limitations = list(dict.fromkeys([*request.limitations, *request.taxonomy_warnings]))
    for item in request.evidence_items:
        limitations.extend(item.warnings)
    limitations = list(dict.fromkeys(limitations))
    limitations.append(_CAUSALITY_LIMITATION)

    if allow_strain:
        status = AnswerStatus.SUPPORTED
        answer = (
            "可以给出支持性回答：当前证据达到菌株或更强分类学分辨率，"
            "并且每条主张都有可追溯证据。"
        )
    elif allow_species:
        status = AnswerStatus.PARTIALLY_SUPPORTED
        answer = (
            "可以部分支持这个判断：文献层面存在物种级相关证据，"
            "但还不能把它提升为当前样本或具体菌株已经生产天然产物的结论。"
        )
    elif _tier_rank(strongest_tier) >= _tier_rank("C"):
        status = AnswerStatus.PARTIALLY_SUPPORTED
        answer = (
            "不能直接证明样本中存在已确认的天然产物生产。"
            "目前召回到的是属级或更弱的候选证据，最多支持“值得进一步验证的天然产物潜力线索”。"
        )
    else:
        status = AnswerStatus.INSUFFICIENT_EVIDENCE
        answer = "现有证据过弱，无法给出实质性回答。"

    return GroundedAnswer(
        status=status,
        answer=answer,
        claims=claims,
        evidence_refs=refs,
        limitations=limitations,
        suggested_validations=[
            "请验证查询生物的分类学解析。",
            "请用正交分析方法确认代谢物身份。",
        ],
        writer_mode="fallback",
        provenance={"writer": "rhizonp.writer.fallback_writer", "strongest_tier": strongest_tier},
    )
