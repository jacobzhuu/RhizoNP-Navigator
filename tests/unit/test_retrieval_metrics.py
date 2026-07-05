from rhizonp.evaluation.retrieval_metrics import mrr_at_k, ndcg_at_k, recall_at_k


def test_recall_mrr_and_ndcg_metrics() -> None:
    relevant = {"a", "b"}
    retrieved = ["x", "a", "b", "y"]

    assert recall_at_k(relevant, retrieved, 5) == 1.0
    assert recall_at_k(relevant, retrieved, 1) == 0.0
    assert mrr_at_k(relevant, retrieved, 5) == 0.5
    assert ndcg_at_k(relevant, retrieved, 4) > 0.0
    assert ndcg_at_k(set(), retrieved, 4) == 0.0
