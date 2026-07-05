from __future__ import annotations

import pytest

from rhizonp.config import get_settings


@pytest.fixture(autouse=True)
def isolate_runtime_secrets(monkeypatch: pytest.MonkeyPatch):
    """Keep local .env credentials from changing deterministic test behavior."""

    for env_name in (
        "DEEPSEEK_API_KEY",
        "QWEN_API_KEY",
        "POSTGRES_PASSWORD",
        "NCBI_API_KEY",
    ):
        monkeypatch.setenv(env_name, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
