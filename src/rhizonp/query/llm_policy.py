from __future__ import annotations

from rhizonp.config import Settings, get_settings


def resolve_use_llm(requested: bool | None, settings: Settings | None = None) -> bool:
    if requested is not None:
        return requested
    resolved = settings or get_settings()
    return resolved.ask_default_use_llm
