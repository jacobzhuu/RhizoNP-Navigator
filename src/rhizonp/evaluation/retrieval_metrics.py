from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


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
