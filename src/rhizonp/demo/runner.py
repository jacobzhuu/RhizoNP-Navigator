from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature.retrieval import SearchFilters, search_paper_chunks
from rhizonp.omics.pipeline import (
    export_candidate_matrix_csv,
    export_pipeline_json,
    run_own_data_pipeline,
)
from rhizonp.storage.postgres import create_session_factory
from rhizonp.taxonomy.grading import grade_evidence
from rhizonp.writer.models import EvidenceInput, WriterRequest
from rhizonp.writer.service import write_grounded_answer

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "demo"


@dataclass(frozen=True)
class DemoCaseResult:
    case_id: str
    title: str
    status: str
    outputs: dict[str, str] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DemoRunResult:
    cases: list[DemoCaseResult]
    output_dir: Path
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cases": [
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "status": case.status,
                    "outputs": dict(case.outputs),
                    "payload": case.payload,
                }
                for case in self.cases
            ],
            "output_dir": str(self.output_dir),
            "provenance": dict(self.provenance),
        }


def _literature_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    load_phase2_literature_fixture(session)
    session.commit()
    return session


def run_demo_case_1_literature_retrieval(output_dir: Path) -> DemoCaseResult:
    session = _literature_session()
    try:
        results = search_paper_chunks(
            session,
            "Streptomyces rhizosphere natural product",
            top_k=5,
            filters=SearchFilters(sections=("results",), taxa=("Streptomyces",)),
            retrieval_mode="bm25",
        )
    finally:
        session.close()

    payload = {
        "query": "Streptomyces rhizosphere natural product",
        "result_count": len(results),
        "results": [
            {
                "rank": result.rank,
                "score": result.score,
                "text": result.text,
                "trace": {
                    "chunk_id": str(result.chunk_id),
                    "paper_id": str(result.paper_id),
                    "doi": result.doi,
                    "source_url": result.source_url,
                    "section": result.section,
                },
            }
            for result in results
        ],
    }
    json_path = output_dir / "case1_literature_retrieval.json"
    md_path = output_dir / "case1_literature_retrieval.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Demo Case 1: Literature Evidence Retrieval",
                "",
                "Question: plant-microbe / rhizosphere Streptomyces natural product evidence",
                "",
                f"Retrieved {len(results)} chunks with full provenance trace.",
                "",
                "## Top Result",
                "",
                results[0].text if results else "No results.",
            ]
        ),
        encoding="utf-8",
    )
    return DemoCaseResult(
        case_id="case1",
        title="Literature evidence retrieval for plant-microbe / rhizosphere question",
        status="ok" if results else "empty",
        outputs={"json": str(json_path), "markdown": str(md_path)},
        payload=payload,
    )


def run_demo_case_2_taxonomy_safety(output_dir: Path) -> DemoCaseResult:
    grading = grade_evidence(
        "Streptomyces",
        "Streptomyces hygroscopicus OS-2",
        observation_method="synthetic_16S_fixture",
    )
    payload = grading.to_dict()
    json_path = output_dir / "case2_taxonomy_grading.json"
    md_path = output_dir / "case2_taxonomy_grading.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Demo Case 2: Taxonomy-aware Evidence Grading",
                "",
                "Query taxon: Streptomyces (genus-level 16S observation)",
                "Literature taxon: Streptomyces hygroscopicus OS-2 (strain-level record)",
                "",
                f"- Taxonomy distance: {grading.taxonomy_distance.value}",
                f"- Evidence tier: {grading.evidence_tier.value}",
                f"- Max supported claim: {grading.max_supported_claim}",
                "",
                "## Warnings",
                "",
                *[f"- {warning}" for warning in grading.warnings],
            ]
        ),
        encoding="utf-8",
    )
    return DemoCaseResult(
        case_id="case2",
        title="Taxonomy-aware grading with genus-to-strain overclaim prevention",
        status="ok",
        outputs={"json": str(json_path), "markdown": str(md_path)},
        payload=payload,
    )


def run_demo_case_3_own_data_pipeline(output_dir: Path) -> DemoCaseResult:
    pipeline_result = run_own_data_pipeline(PROJECT_ROOT / "data" / "fixtures" / "own_data_demo")
    json_path = export_pipeline_json(pipeline_result, output_dir / "case3_own_data_pipeline.json")
    csv_path = export_candidate_matrix_csv(
        pipeline_result,
        output_dir / "case3_candidate_matrix.csv",
    )
    top_links = []
    for association_result in pipeline_result.association_results:
        matrix = association_result.candidate_matrix
        if matrix.rows:
            top = matrix.rows[0]
            top_links.append(
                {
                    "association_id": association_result.association.association_id,
                    "source_raw_label": association_result.association.source_raw_label,
                    "target_raw_label": association_result.association.target_raw_label,
                    "compound_name": top.compound_name,
                    "evidence_tier": top.evidence_tier,
                    "status": top.status,
                }
            )

    writer_answer = None
    if pipeline_result.association_results:
        first = pipeline_result.association_results[0]
        if first.candidate_matrix.rows:
            top = first.candidate_matrix.rows[0]
            writer_answer = write_grounded_answer(
                WriterRequest(
                    question=(
                        f"Can {first.taxon.raw_label} be linked to {first.metabolite.raw_label} "
                        "with external natural product evidence?"
                    ),
                    evidence_items=[
                        EvidenceInput(
                            evidence_id=__import__("uuid").uuid4(),
                            claim_type="taxon_produces_compound",
                            predicate="PRODUCES",
                            object_literal=top.compound_name,
                            evidence_tier=top.evidence_tier,
                            confidence=top.score,
                            supporting_span=f"Synthetic fixture link to {top.compound_name}.",
                            taxonomy_distance=top.taxonomy_distance,
                            warnings=top.warnings,
                        )
                    ],
                    taxonomy_warnings=top.warnings,
                    limitations=first.limitations,
                )
            ).model_dump(mode="json")

    payload = {
        "association_count": len(pipeline_result.association_results),
        "top_links": top_links,
        "writer_answer": writer_answer,
    }
    md_path = output_dir / "case3_own_data_pipeline.md"
    md_path.write_text(
        "\n".join(
            [
                "# Demo Case 3: Own-data-to-literature",
                "",
                "Synthetic 16S/LC-MS association fixture linked to natural-product candidates.",
                "",
                f"- Associations processed: {len(pipeline_result.association_results)}",
                f"- Candidate matrix CSV: {csv_path.name}",
                "",
                "## Top Candidate Links",
                "",
                *[
                    f"- {item['source_raw_label']} -> {item['target_raw_label']}: "
                    f"{item['compound_name']} ({item['evidence_tier']}, {item['status']})"
                    for item in top_links
                ],
            ]
        ),
        encoding="utf-8",
    )
    return DemoCaseResult(
        case_id="case3",
        title="Own-data-to-literature with synthetic 16S/LC-MS associations",
        status="ok" if pipeline_result.association_results else "empty",
        outputs={
            "json": str(json_path),
            "csv": str(csv_path),
            "markdown": str(md_path),
        },
        payload=payload,
    )


def run_all_demos(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> DemoRunResult:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    cases = [
        run_demo_case_1_literature_retrieval(directory),
        run_demo_case_2_taxonomy_safety(directory),
        run_demo_case_3_own_data_pipeline(directory),
    ]
    summary_path = directory / "demo_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "cases": [case.case_id for case in cases],
                "statuses": {case.case_id: case.status for case in cases},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path = directory / "demo_report.md"
    report_path.write_text(_render_demo_report(cases), encoding="utf-8")
    return DemoRunResult(
        cases=cases,
        output_dir=directory,
        provenance={
            "demo_runner": "rhizonp.demo.runner",
            "offline": True,
            "network_required": False,
            "summary_json": str(summary_path),
            "report_markdown": str(report_path),
        },
    )


def _render_demo_report(cases: list[DemoCaseResult]) -> str:
    lines = [
        "# RhizoNP Navigator Demo Report",
        "",
        "Deterministic offline demo using synthetic fixtures only.",
        "",
    ]
    for case in cases:
        lines.extend(
            [
                f"## {case.case_id}: {case.title}",
                "",
                f"Status: `{case.status}`",
                "",
                "Outputs:",
                "",
                *[f"- {key}: `{path}`" for key, path in case.outputs.items()],
                "",
            ]
        )
    return "\n".join(lines)


def run_smoke_checks() -> dict[str, Any]:
    output_dir = PROJECT_ROOT / "data" / "output" / "smoke"
    demo = run_all_demos(output_dir)
    checks = {
        "case_count": len(demo.cases),
        "all_cases_ok": all(case.status == "ok" for case in demo.cases),
        "outputs_exist": all(
            Path(path).exists() for case in demo.cases for path in case.outputs.values()
        ),
    }
    checks["passed"] = checks["case_count"] == 3 and checks["all_cases_ok"] and checks["outputs_exist"]
    return checks
