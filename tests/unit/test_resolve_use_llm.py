from __future__ import annotations

from rhizonp.config import Settings
from rhizonp.query.llm_policy import resolve_use_llm


def test_resolve_use_llm_defaults_to_settings() -> None:
    settings = Settings(ask_default_use_llm=True)
    assert resolve_use_llm(None, settings) is True
    settings_off = Settings(ask_default_use_llm=False)
    assert resolve_use_llm(None, settings_off) is False


def test_resolve_use_llm_explicit_override() -> None:
    settings = Settings(ask_default_use_llm=True)
    assert resolve_use_llm(False, settings) is False
    assert resolve_use_llm(True, settings) is True
