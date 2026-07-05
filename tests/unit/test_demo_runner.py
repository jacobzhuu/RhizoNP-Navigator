from __future__ import annotations

from pathlib import Path

from rhizonp.demo.runner import run_all_demos, run_smoke_checks


def test_smoke_checks_pass_offline() -> None:
    result = run_smoke_checks()
    assert result["case_count"] == 3
    assert result["passed"] is True


def test_demo_writes_all_case_outputs(tmp_path: Path) -> None:
    demo = run_all_demos(tmp_path)
    assert len(demo.cases) == 3
    for case in demo.cases:
        assert case.status == "ok"
        for output_path in case.outputs.values():
            assert Path(output_path).exists()
