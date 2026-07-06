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


def _has_strain_claim_blocking_warning(warnings: Sequence[str]) -> bool:
    for warning in warnings:
        normalized = warning.casefold()
        has_strain_scope = "strain-level production" in normalized or "菌株水平" in warning
        has_blocking_language = any(
            token in normalized
            for token in ("cannot", "must not", "not support", "forbid", "不得", "不能", "不支持")
        )
        if has_strain_scope and has_blocking_language:
            return True
    return False


def _is_direct_support(item: EvidenceInput) -> bool:
    return item.predicate.upper() in {"PRODUCES", "SUPPORTS"} and item.directness == "direct"


def _select_answer_evidence(
    evidence_items: Sequence[EvidenceInput],
    *,
    strongest_tier: str,
    status: AnswerStatus,
) -> list[EvidenceInput]:
    if status == AnswerStatus.SUPPORTED:
        direct_items = [
            item
            for item in evidence_items
            if _is_direct_support(item) and _tier_rank(item.evidence_tier) == _tier_rank(strongest_tier)
        ]
        if direct_items:
            return direct_items
    strongest_items = [
        item
        for item in evidence_items
        if _tier_rank(item.evidence_tier) == _tier_rank(strongest_tier)
    ]
    return strongest_items or list(evidence_items)


def _unique_objects(evidence_items: Sequence[EvidenceInput]) -> list[str]:
    values = [item.object_literal for item in evidence_items if item.object_literal]
    return list(dict.fromkeys(values))


def _has_fixture_warning(evidence_items: Sequence[EvidenceInput]) -> bool:
    for item in evidence_items:
        provenance = item.provenance or {}
        if provenance.get("is_fixture") or provenance.get("fixture"):
            return True
        if any("fixture" in warning.casefold() for warning in item.warnings):
            return True
    return False


def _evidence_source_summary(item: EvidenceInput) -> str:
    provenance = item.provenance or {}
    source = provenance.get("source_database") or provenance.get("source_type")
    record_id = (
        provenance.get("external_record_id")
        or provenance.get("npaid")
        or provenance.get("record_key")
    )
    details: list[str] = []
    if source:
        details.append(str(source))
    if record_id:
        details.append(str(record_id))
    if provenance.get("doi"):
        details.append(f"DOI {provenance['doi']}")
    if provenance.get("pmid"):
        details.append(f"PMID {provenance['pmid']}")
    return "，".join(details)


def _answer_for_status(
    *,
    status: AnswerStatus,
    strongest_tier: str,
    selected_evidence: Sequence[EvidenceInput],
) -> str:
    objects = _unique_objects(selected_evidence)
    target = "、".join(objects[:3]) if objects else "目标对象"
    source_summary = _evidence_source_summary(selected_evidence[0]) if selected_evidence else ""
    source_sentence = f"核心证据来源为 {source_summary}。" if source_summary else ""
    fixture_note = ""
    has_fixture_warning = _has_fixture_warning(selected_evidence)
    if has_fixture_warning:
        fixture_note = (
            "但这里的强证据来自 fixture/test 语料，适合用于现场演示证据分级、引用追踪和写作流程；"
            "如果要作为真实科研结论，需要替换为真实文献、结构化天然产物数据库或原始实验记录。"
        )

    if status == AnswerStatus.SUPPORTED:
        return (
            f"可以给出支持性回答：当前证据包中存在与 {target} 相关的直接生产证据，"
            f"且最高证据等级为 {strongest_tier}，达到菌株级或更强的分类学分辨率。"
            f"{source_sentence}"
            "这意味着系统不是仅根据属级共现或泛泛综述来回答，而是把“同一菌株/直接生产关系”"
            "作为支撑结论的核心依据。"
            f"{fixture_note}\n\n"
            f"因此，在{'当前演示数据范围内' if has_fixture_warning else '当前知识库和结构化数据范围内'}，"
            "可以回答“有生产证据”。同时，结论边界仍然需要保留："
            "召回到的较弱背景片段不能单独证明生产关系，真正用于支撑最终结论的是可追溯的直接证据条目。"
        )
    if status == AnswerStatus.PARTIALLY_SUPPORTED and tier_allows_species_claim(strongest_tier):
        return (
            f"可以部分支持这个判断：当前证据最高达到 {strongest_tier}，说明文献或结构化记录中"
            "存在物种级相关线索，但它还不足以证明用户样本中的具体菌株已经生产目标天然产物。"
            "系统因此会保留“有较强候选依据”的表述，而不会升级成菌株级生产结论。\n\n"
            "更稳妥的解读是：该结果适合用于优先级排序和后续验证设计，而不是直接作为最终生物合成事实。"
        )
    if status == AnswerStatus.PARTIALLY_SUPPORTED:
        return (
            f"不能直接证明样本中存在已确认的天然产物生产。当前最高证据等级为 {strongest_tier}，"
            "主要支持的是属级、共现或检索线索层面的候选关系；这些线索可以说明该方向值得继续追踪，"
            "但不能替代同一菌株的产物分离、基因簇表达或结构确认。\n\n"
            "因此，系统给出的保守结论是“部分支持”：可作为挖掘候选和实验设计入口，"
            "但不应表述为已确认生产。"
        )
    return (
        "现有证据过弱，无法给出实质性回答。当前召回结果没有形成可追溯、足够直接的证据链，"
        "系统因此拒绝把相关文献或文本共现改写成事实性结论。"
    )


def _build_claims(
    request: WriterRequest,
    *,
    allow_strain_claim: bool,
    allow_species_claim: bool,
    evidence_items: Sequence[EvidenceInput] | None = None,
) -> list[Claim]:
    claims: list[Claim] = []
    merged_claim_refs: dict[tuple[str, str], list] = {}
    items = evidence_items if evidence_items is not None else request.evidence_items
    for item in items:
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

        if _is_direct_support(item):
            source_summary = _evidence_source_summary(item)
            claim_text = (
                f"直接证据（{item.evidence_tier}）支持 {item.object_literal or '目标对象'} "
                "与查询菌株之间存在生产关系"
            )
            if source_summary:
                claim_text += f"；来源：{source_summary}。"
            else:
                claim_text += "。"
        else:
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
    allow_strain = tier_allows_strain_claim(strongest_tier) and not _has_strain_claim_blocking_warning(
        request.taxonomy_warnings
    )
    allow_species = tier_allows_species_claim(strongest_tier)
    if allow_strain:
        status = AnswerStatus.SUPPORTED
    elif allow_species:
        status = AnswerStatus.PARTIALLY_SUPPORTED
    elif _tier_rank(strongest_tier) >= _tier_rank("C"):
        status = AnswerStatus.PARTIALLY_SUPPORTED
    else:
        status = AnswerStatus.INSUFFICIENT_EVIDENCE

    selected_evidence = _select_answer_evidence(
        request.evidence_items,
        strongest_tier=strongest_tier,
        status=status,
    )
    claims = _build_claims(
        request,
        allow_strain_claim=allow_strain,
        allow_species_claim=allow_species,
        evidence_items=selected_evidence,
    )
    refs = [item.evidence_id for item in selected_evidence]

    limitations = list(dict.fromkeys([*request.limitations, *request.taxonomy_warnings]))
    for item in selected_evidence:
        limitations.extend(item.warnings)
    limitations = list(dict.fromkeys(limitations))
    limitations.append(_CAUSALITY_LIMITATION)
    answer = _answer_for_status(
        status=status,
        strongest_tier=strongest_tier,
        selected_evidence=selected_evidence,
    )

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
