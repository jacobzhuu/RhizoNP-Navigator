from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rhizonp.linking.compound_normalization import normalize_compound_name
from rhizonp.linking.models import NaturalProductFixtureRecord
from rhizonp.linking.np_adapter import load_natural_product_fixture
from rhizonp.taxonomy.grading import grade_evidence
from rhizonp.taxonomy.models import EvidenceTier


@dataclass(frozen=True)
class CandidateMatrixRow:
    rank: int
    query_taxon: str
    compound_name: str
    producer_taxon: str
    taxonomy_distance: str
    evidence_tier: str
    compound_match: bool
    evidence_count: int
    score: float
    status: str
    bioactivity: dict[str, Any] | None
    warnings: list[str]
    limitations: list[str]
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "query_taxon": self.query_taxon,
            "compound_name": self.compound_name,
            "producer_taxon": self.producer_taxon,
            "taxonomy_distance": self.taxonomy_distance,
            "evidence_tier": self.evidence_tier,
            "compound_match": self.compound_match,
            "evidence_count": self.evidence_count,
            "score": self.score,
            "status": self.status,
            "bioactivity": self.bioactivity,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class CandidateMatrix:
    query_taxon: str
    metabolite_name: str | None
    rows: list[CandidateMatrixRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_taxon": self.query_taxon,
            "metabolite_name": self.metabolite_name,
            "rows": [row.to_dict() for row in self.rows],
        }


def _tier_score(tier: EvidenceTier) -> float:
    return {
        EvidenceTier.A: 1.0,
        EvidenceTier.B: 0.75,
        EvidenceTier.C: 0.4,
        EvidenceTier.D: 0.1,
    }[tier]


def _status_from_tier(
    tier: EvidenceTier,
    warnings: list[str],
    *,
    compound_match: bool,
    metabolite_queried: bool,
) -> str:
    if metabolite_queried and not compound_match:
        return "PARTIALLY_SUPPORTED"
    if warnings:
        return "PARTIALLY_SUPPORTED"
    if tier in {EvidenceTier.A, EvidenceTier.B}:
        return "SUPPORTED"
    if tier == EvidenceTier.C:
        return "PARTIALLY_SUPPORTED"
    return "INSUFFICIENT_EVIDENCE"


def _score_candidate(
    *,
    tier: EvidenceTier,
    compound_match: bool,
    evidence_count: int,
) -> float:
    compound_component = 0.25 if compound_match else 0.0
    return round(
        _tier_score(tier) * 0.6 + compound_component + min(evidence_count, 3) * 0.05,
        4,
    )


def link_natural_product_candidates(
    query_taxon: str,
    *,
    metabolite_name: str | None = None,
    observation_method: str | None = None,
    fixture_path: str | None = None,
) -> CandidateMatrix:
    kwargs: dict[str, Any] = {}
    if fixture_path is not None:
        kwargs["fixture_path"] = fixture_path

    records = load_natural_product_fixture(**kwargs)
    normalized_metabolite = None
    if metabolite_name:
        normalize_kwargs: dict[str, Any] = {}
        if fixture_path is not None:
            normalize_kwargs["fixture_path"] = fixture_path
        normalized_metabolite = normalize_compound_name(metabolite_name, **normalize_kwargs)

    scored_rows: list[tuple[float, CandidateMatrixRow]] = []
    for record in records:
        row = _build_row(
            query_taxon=query_taxon,
            record=record,
            normalized_metabolite=normalized_metabolite,
            observation_method=observation_method,
        )
        scored_rows.append((row.score, row))

    scored_rows.sort(key=lambda item: item[0], reverse=True)
    ranked_rows: list[CandidateMatrixRow] = []
    for index, (_, row) in enumerate(scored_rows, start=1):
        ranked_rows.append(
            CandidateMatrixRow(
                rank=index,
                query_taxon=row.query_taxon,
                compound_name=row.compound_name,
                producer_taxon=row.producer_taxon,
                taxonomy_distance=row.taxonomy_distance,
                evidence_tier=row.evidence_tier,
                compound_match=row.compound_match,
                evidence_count=row.evidence_count,
                score=row.score,
                status=row.status,
                bioactivity=row.bioactivity,
                warnings=row.warnings,
                limitations=row.limitations,
                provenance=row.provenance,
            )
        )
    return CandidateMatrix(
        query_taxon=query_taxon,
        metabolite_name=metabolite_name,
        rows=ranked_rows,
    )


def _build_row(
    *,
    query_taxon: str,
    record: NaturalProductFixtureRecord,
    normalized_metabolite: str | None,
    observation_method: str | None,
) -> CandidateMatrixRow:
    grading = grade_evidence(
        query_taxon,
        record.producer_taxon,
        observation_method=observation_method,
    )
    compound_match = (
        normalized_metabolite is not None
        and normalize_compound_name(normalized_metabolite) == record.compound_name
    )
    metabolite_queried = normalized_metabolite is not None
    evidence_count = 1
    score = _score_candidate(
        tier=grading.evidence_tier,
        compound_match=compound_match,
        evidence_count=evidence_count,
    )
    bioactivity = None
    if record.bioactivity is not None:
        bioactivity = {
            "activity_type": record.bioactivity.activity_type,
            "target": record.bioactivity.target,
            "evidence_level": record.bioactivity.evidence_level,
        }

    limitations = list(grading.limitations)
    if metabolite_queried and not compound_match:
        limitations.append(
            "Metabolite feature did not match any known compound name; "
            "link is taxonomy-compatible only."
        )

    return CandidateMatrixRow(
        rank=0,
        query_taxon=query_taxon,
        compound_name=record.compound_name,
        producer_taxon=record.producer_taxon,
        taxonomy_distance=grading.taxonomy_distance.value,
        evidence_tier=grading.evidence_tier.value,
        compound_match=compound_match,
        evidence_count=evidence_count,
        score=score,
        status=_status_from_tier(
            grading.evidence_tier,
            grading.warnings,
            compound_match=compound_match,
            metabolite_queried=metabolite_queried,
        ),
        bioactivity=bioactivity,
        warnings=grading.warnings,
        limitations=limitations,
        provenance={
            "source_database": record.source_database,
            "external_record_id": record.external_record_id,
            "record_key": record.key,
            **record.provenance,
        },
    )
