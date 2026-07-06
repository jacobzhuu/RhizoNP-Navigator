from __future__ import annotations

from tests.unit.test_api_readonly import _client_with_phase2_literature_fixture


def test_ask_persists_history_and_returns_history_id() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.post(
        "/api/v1/ask",
        json={
            "question": "Bacillus 是否有天然产物生产证据？",
            "retrieval_mode": "bm25",
            "top_k": 2,
            "max_queries": 1,
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["history_id"]

    list_response = client.get("/api/v1/history?kind=ask")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] >= 1
    item = next(row for row in listed["items"] if row["history_id"] == payload["history_id"])
    assert item["kind"] == "ask"
    assert item["title"] == "Bacillus 是否有天然产物生产证据？"
    assert item["status"]
    assert "response_payload" not in item
    assert "request" not in item

    detail_response = client.get(f"/api/v1/history/{payload['history_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["kind"] == "ask"
    assert detail["request"]["question"] == "Bacillus 是否有天然产物生产证据？"
    assert detail["response"]["answer"]["status"]


def test_results_interpret_persists_history() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.post(
        "/api/v1/results/interpret",
        json={
            "taxon": "Streptomyces",
            "metabolite": "M1023",
            "association_direction": "positive",
            "effect_size": 0.72,
            "p_value": 0.003,
            "observation_method": "16S genus-level",
            "use_llm": False,
            "retrieval_mode": "bm25",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["history_id"]

    list_response = client.get("/api/v1/history?kind=results")
    assert list_response.status_code == 200
    listed = list_response.json()
    item = next(row for row in listed["items"] if row["history_id"] == payload["history_id"])
    assert item["kind"] == "results"
    assert item["title"] == "Streptomyces · M1023"

    detail_response = client.get(f"/api/v1/history/{payload['history_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["response"]["finding_count"] == 1
    assert detail["request"]["taxon"] == "Streptomyces"


def test_results_demo_does_not_persist_history() -> None:
    client = _client_with_phase2_literature_fixture()

    before = client.get("/api/v1/history?kind=results")
    assert before.status_code == 200
    total_before = before.json()["total"]

    response = client.post(
        "/api/v1/results/demo",
        json={"use_llm": False, "retrieval_mode": "bm25", "top_k": 2},
    )
    assert response.status_code == 200
    assert response.json().get("history_id") is None

    after = client.get("/api/v1/history?kind=results")
    assert after.status_code == 200
    assert after.json()["total"] == total_before


def test_get_history_returns_404_for_missing_record() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.get("/api/v1/history/00000000-0000-0000-0000-000000000099")

    assert response.status_code == 404
