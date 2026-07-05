from __future__ import annotations

from rhizonp.evaluation.retrieval_metrics import (
    PRIMARY_RELEVANCE_MIN_GRADE,
    STRICT_RELEVANCE_MIN_GRADE,
    graded_mrr_at_k,
    graded_ndcg_at_k,
    graded_recall_at_k,
    strict_graded_recall_at_k,
)


def test_primary_and_strict_threshold_constants() -> None:
    assert PRIMARY_RELEVANCE_MIN_GRADE == 1
    assert STRICT_RELEVANCE_MIN_GRADE == 2


def test_graded_recall_counts_grade_one_and_two_as_relevant() -> None:
    grades = {"1": 2, "2": 1, "3": 0}
    retrieved = ["3", "1", "2"]
    assert graded_recall_at_k(grades, retrieved, 3) == 1.0


def test_graded_recall_partial_at_k() -> None:
    grades = {"1": 2, "2": 1}
    retrieved = ["9", "1"]
    assert graded_recall_at_k(grades, retrieved, 2) == 0.5


def test_graded_mrr_uses_first_relevant_pmid() -> None:
    grades = {"1": 2, "2": 1}
    retrieved = ["9", "2", "1"]
    assert graded_mrr_at_k(grades, retrieved, 10) == 0.5


def test_graded_ndcg_uses_grade_gains() -> None:
    grades = {"1": 2, "2": 1}
    retrieved = ["1", "2"]
    assert graded_ndcg_at_k(grades, retrieved, 10) == 1.0

    worse = ["2", "9", "1"]
    assert graded_ndcg_at_k(grades, worse, 10) < 1.0


def test_strict_recall_counts_only_grade_two() -> None:
    grades = {"1": 2, "2": 1, "3": 2}
    retrieved = ["2", "1", "3"]
    assert strict_graded_recall_at_k(grades, retrieved, 3) == 1.0
    retrieved_miss = ["2"]
    assert strict_graded_recall_at_k(grades, retrieved_miss, 3) == 0.0


def test_unjudged_retrieved_pmid_does_not_count_as_irrelevant_in_recall() -> None:
    grades = {"1": 2}
    retrieved = ["9", "1"]
    assert graded_recall_at_k(grades, retrieved, 2) == 1.0


def test_unjudged_retrieved_pmid_contributes_zero_ndcg_gain() -> None:
    grades = {"1": 2, "2": 1}
    with_unjudged = ["9", "1", "2"]
    # Unjudged PMIDs add zero gain but still consume rank positions in DCG.
    assert graded_ndcg_at_k(grades, with_unjudged, 10) < graded_ndcg_at_k(grades, ["1", "2"], 10)
    assert graded_ndcg_at_k(grades, with_unjudged, 10) > 0.0
