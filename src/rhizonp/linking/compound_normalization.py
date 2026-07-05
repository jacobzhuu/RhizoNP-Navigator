from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from rhizonp.config import PROJECT_ROOT

DEFAULT_COMPOUND_FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "natural_products_demo.json"


def _normalize_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


@lru_cache
def _load_compound_aliases(path: str) -> dict[str, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    aliases = payload.get("compound_aliases", {})
    return {_normalize_key(key): value for key, value in aliases.items()}


def normalize_compound_name(
    name: str,
    *,
    fixture_path: str | Path = DEFAULT_COMPOUND_FIXTURE_PATH,
) -> str:
    aliases = _load_compound_aliases(str(fixture_path))
    canonical = aliases.get(_normalize_key(name))
    if canonical:
        return canonical
    return name.strip()
