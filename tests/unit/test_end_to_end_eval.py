from __future__ import annotations

from pathlib import Path

from rhizonp.config import PROJECT_ROOT
from rhizonp.evaluation.end_to_end import (
    run_end_to_end_evaluation,
    write_evaluation_reports,
)


def test_end_to_end_evaluation_runs_offline() -> None:
    report = run_end_to_end_evaluation(
        PROJECT_ROOT / "data" / "eval" / "end_to_end_cases.json"
    )
    assert report.benchmark_id == "phase7_end_to_end_mini"
    assert "recall_at_10" in report.retrieval
    assert report.taxonomy_safety["passed_cases"] >= 1
    assert report.abstention["abstention_accuracy"] == 1.0
    assert report.conflict["conflict_detection_rate"] == 1.0


def test_end_to_end_reports_written(tmp_path: Path) -> None:
    report = run_end_to_end_evaluation(
        PROJECT_ROOT / "data" / "eval" / "end_to_end_cases.json"
    )
    json_path, md_path = write_evaluation_reports(report, tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert "Recall@10" in md_path.read_text(encoding="utf-8")
