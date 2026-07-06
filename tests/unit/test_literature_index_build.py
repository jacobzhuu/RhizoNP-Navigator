from __future__ import annotations

from pathlib import Path

from rhizonp.literature.index_store import _atomic_replace_current, read_current_build_id


def test_current_pointer_atomic_replace(tmp_path: Path) -> None:
    index_root = tmp_path / "rhizonp_domain_v1"
    index_root.mkdir()
    _atomic_replace_current(index_root, "rev_1_abc")
    assert read_current_build_id(index_root) == "rev_1_abc"
    _atomic_replace_current(index_root, "rev_2_def")
    assert read_current_build_id(index_root) == "rev_2_def"
