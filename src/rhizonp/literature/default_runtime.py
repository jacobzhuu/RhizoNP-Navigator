from __future__ import annotations

from rhizonp.literature.runtime import LiteratureRetrievalRuntime, build_offline_literature_runtime

_default_runtime: LiteratureRetrievalRuntime | None = None


def set_default_literature_runtime(runtime: LiteratureRetrievalRuntime | None) -> None:
    global _default_runtime
    _default_runtime = runtime


def get_default_literature_runtime() -> LiteratureRetrievalRuntime:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = build_offline_literature_runtime()
    return _default_runtime
