from rhizonp.get_answer import BGEReranker, NoReranker


class FakeFlagReranker:
    def __init__(self, model_name: str, *, use_fp16: bool) -> None:
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.pairs: list[list[str]] = []

    def compute_score(self, pairs: list[list[str]]) -> list[float]:
        self.pairs = pairs
        return [float(len(passage)) for _query, passage in pairs]


def test_no_reranker_returns_neutral_scores() -> None:
    reranker = NoReranker()

    assert reranker.score("query", ["a", "bb"]) == [0.0, 0.0]


def test_bge_reranker_uses_flag_reranker_pairs() -> None:
    created_models: list[FakeFlagReranker] = []

    def factory(model_name: str, *, use_fp16: bool) -> FakeFlagReranker:
        model = FakeFlagReranker(model_name, use_fp16=use_fp16)
        created_models.append(model)
        return model

    reranker = BGEReranker("BAAI/bge-reranker-v2-m3", model_factory=factory)
    scores = reranker.score("streptomyces", ["short", "longer passage"])

    assert scores == [5.0, 14.0]
    assert created_models[0].model_name == "BAAI/bge-reranker-v2-m3"
    assert created_models[0].pairs == [
        ["streptomyces", "short"],
        ["streptomyces", "longer passage"],
    ]
