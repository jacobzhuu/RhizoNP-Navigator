from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence


def recall_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def reciprocal_rank(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    for rank, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def mrr_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    return reciprocal_rank(relevant, retrieved, k)


def ndcg_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    if not relevant:
        return 0.0

    def dcg(items: Sequence[str]) -> float:
        score = 0.0
        for index, item in enumerate(items, start=1):
            if item in relevant:
                score += 1.0 / math.log2(index + 1)
        return score

    ideal_hits = min(len(relevant), k)
    ideal = [1.0] * ideal_hits
    ideal_dcg = sum(value / math.log2(index + 2) for index, value in enumerate(ideal))
    if ideal_dcg == 0.0:
        return 0.0
    return dcg(retrieved[:k]) / ideal_dcg


def aggregate_metric(values: Iterable[float]) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)


def _relevant_pmids(grades: Mapping[str, int], *, min_grade: int = 1) -> set[str]:
    return {pmid for pmid, grade in grades.items() if grade >= min_grade}


def graded_recall_at_k(grades: Mapping[str, int], retrieved: Sequence[str], k: int) -> float:
    """Recall@k using paper-level PMIDs; grades >= 1 count as relevant."""
    relevant = _relevant_pmids(grades)
    return recall_at_k(relevant, retrieved, k)


def graded_mrr_at_k(grades: Mapping[str, int], retrieved: Sequence[str], k: int) -> float:
    relevant = _relevant_pmids(grades)
    return mrr_at_k(relevant, retrieved, k)


def graded_ndcg_at_k(grades: Mapping[str, int], retrieved: Sequence[str], k: int) -> float:
    """nDCG@k with graded gains (0, 1, 2) for paper-level PMIDs."""
    if not grades:
        return 0.0

    def dcg(items: Sequence[str]) -> float:
        score = 0.0
        for index, item in enumerate(items[:k], start=1):
            gain = float(grades.get(item, 0))
            if gain > 0.0:
                score += gain / math.log2(index + 1)
        return score

    ideal_gains = sorted((float(grade) for grade in grades.values() if grade > 0), reverse=True)
    ideal_gains = ideal_gains[:k]
    if not ideal_gains:
        return 0.0
    ideal_dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(ideal_gains))
    if ideal_dcg == 0.0:
        return 0.0
    return dcg(retrieved) / ideal_dcg
