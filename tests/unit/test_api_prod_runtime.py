from __future__ import annotations

import importlib
from unittest.mock import patch

from fastapi.testclient import TestClient

app_module = importlib.import_module("rhizonp.api.app")


def test_own_data_requires_data_dir_in_prod_mode() -> None:
    with patch.object(app_module, "is_prod_mode", return_value=True):
        client = TestClient(app_module.create_app())
        response = client.post("/api/v1/own-data/pipeline", json={})

    assert response.status_code == 400
    assert "data_dir is required" in response.json()["detail"]


def test_writer_retrieve_evidence_rejects_missing_database_in_prod_mode() -> None:
    with patch.object(app_module, "is_prod_mode", return_value=True):
        with patch.object(
            app_module,
            "create_runtime_engine",
            side_effect=RuntimeError("DATABASE_URL is required"),
        ):
            client = TestClient(app_module.create_app())
            response = client.post(
                "/api/v1/writer/answer",
                json={
                    "question": "What evidence exists?",
                    "retrieve_evidence": True,
                },
            )

    assert response.status_code == 503
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "http_503"
