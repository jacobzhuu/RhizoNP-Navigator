from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from rhizonp.linking.compound_normalization import normalize_compound_name
from rhizonp.omics.csv_ingestion import MetaboliteObservation, TaxonObservation


class QueryStrength(str, Enum):
    SPECIFIC = "specific"
    TAXON_FALLBACK = "taxon_fallback"
    WEAK = "weak"


@dataclass(frozen=True)
class QueryConstructionContext:
    taxon_name: str
    metabolite_raw_label: str
    normalized_compound_name: str | None
    compound_identity_known: bool
    chemical_identification_tier: str | None
    observation_method: str | None
    association_score: float | None


@dataclass(frozen=True)
class GeneratedQuery:
    query_text: str
    query_index: int
    rationale: str
    query_strength: QueryStrength


_FEATURE_LABEL_PATTERN = re.compile(r"^feature[_-]", re.IGNORECASE)


def _is_unknown_lcms_feature(
    raw_label: str,
    *,
    feature_id: str | None,
    chemical_identification_tier: str | None,
) -> bool:
    if _FEATURE_LABEL_PATTERN.match(raw_label.strip()):
        return True
    if feature_id and raw_label.strip().casefold() == feature_id.strip().casefold():
        return True
    if chemical_identification_tier and chemical_identification_tier.upper().startswith("C4"):
        return True
    return False


def build_query_context(
    taxon: TaxonObservation,
    metabolite: MetaboliteObservation,
    *,
    association_score: float | None = None,
) -> QueryConstructionContext:
    taxon_name = taxon.raw_label.strip()
    metabolite_label = metabolite.raw_label.strip()
    unknown_feature = _is_unknown_lcms_feature(
        metabolite_label,
        feature_id=metabolite.feature_id,
        chemical_identification_tier=metabolite.chemical_identification_tier,
    )
    normalized = None
    compound_known = False
    if metabolite_label and not unknown_feature:
        normalized = normalize_compound_name(metabolite_label)
        compound_known = bool(normalized)

    return QueryConstructionContext(
        taxon_name=taxon_name,
        metabolite_raw_label=metabolite_label,
        normalized_compound_name=normalized if compound_known else None,
        compound_identity_known=compound_known,
        chemical_identification_tier=metabolite.chemical_identification_tier,
        observation_method=taxon.method,
        association_score=association_score,
    )


def build_literature_queries(
    context: QueryConstructionContext,
    *,
    max_queries: int = 3,
) -> list[GeneratedQuery]:
    """Build a bounded set of deterministic literature queries for an association."""
    if max_queries <= 0:
        return []

    taxon = context.taxon_name.strip()
    if not taxon:
        return []

    queries: list[GeneratedQuery] = []

    if context.compound_identity_known and context.normalized_compound_name:
        compound = context.normalized_compound_name
        candidates = [
            (
                f"{taxon} {compound}",
                "Taxon and known compound name query.",
                QueryStrength.SPECIFIC,
            ),
            (
                f"{taxon} {compound} secondary metabolite",
                "Compound-specific secondary metabolite context.",
                QueryStrength.SPECIFIC,
            ),
            (
                f"{taxon} microbial natural product {compound}",
                "Natural product production context for known compound.",
                QueryStrength.SPECIFIC,
            ),
        ]
        for index, (text, rationale, strength) in enumerate(candidates[:max_queries], start=1):
            queries.append(
                GeneratedQuery(
                    query_text=text,
                    query_index=index,
                    rationale=rationale,
                    query_strength=strength,
                )
            )
        return queries

    # Unknown LC-MS feature or unannotated metabolite: do not embed feature IDs as chemicals.
    fallback_candidates = [
        (
            f"{taxon} secondary metabolites",
            (
                "Taxon-level secondary metabolite query because metabolite "
                f"'{context.metabolite_raw_label}' is not a confirmed compound identity."
            ),
            QueryStrength.TAXON_FALLBACK,
        ),
        (
            f"{taxon} microbial natural products",
            "Taxon-level natural product context without compound-specific claims.",
            QueryStrength.TAXON_FALLBACK,
        ),
    ]
    if context.metabolite_raw_label and not _FEATURE_LABEL_PATTERN.match(context.metabolite_raw_label):
        fallback_candidates.append(
            (
                f"{taxon} rhizosphere metabolite",
                "Weak context query using metabolite context without naming an unconfirmed structure.",
                QueryStrength.WEAK,
            )
        )

    for index, (text, rationale, strength) in enumerate(fallback_candidates[:max_queries], start=1):
        queries.append(
            GeneratedQuery(
                query_text=text,
                query_index=index,
                rationale=rationale,
                query_strength=strength,
            )
        )
    return queries
