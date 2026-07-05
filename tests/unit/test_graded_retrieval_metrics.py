from __future__ import annotations

from rhizonp.evaluation.retrieval_metrics import (
    graded_mrr_at_k,
    graded_ndcg_at_k,
    graded_recall_at_k,
)


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
