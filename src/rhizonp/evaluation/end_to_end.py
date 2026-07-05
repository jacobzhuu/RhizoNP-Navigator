from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base
from rhizonp.evaluation.retrieval_benchmark import (
    DEFAULT_RETRIEVAL_GOLD_PATH,
    evaluate_retrieval_system,
    load_retrieval_benchmark,
)
from rhizonp.evaluation.retrieval_metrics import aggregate_metric
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.linking.candidate_engine import link_natural_product_candidates
from rhizonp.omics.pipeline import run_own_data_pipeline
from rhizonp.storage.postgres import create_session_factory, session_scope
from rhizonp.taxonomy.grading import grade_evidence
from rhizonp.taxonomy.policy import tier_allows_strain_claim
from rhizonp.writer.models import EvidenceInput, WriterRequest
from rhizonp.writer.service import write_grounded_answer

DEFAULT_CASES_PATH = PROJECT_ROOT / "data" / "eval" / "end_to_end_cases.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "eval" / "reports" / "latest"


@dataclass(frozen=True)
class EndToEndEvalReport:
    benchmark_id: str
    description: str
    retrieval: dict[str, Any]
    taxonomy_safety: dict[str, Any]
    linking: dict[str, Any]
    own_data: dict[str, Any]
    abstention: dict[str, Any]
    conflict: dict[str, Any]
    citations: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "description": self.description,
            "retrieval": self.retrieval,
            "taxonomy_safety": self.taxonomy_safety,
            "linking": self.linking,
            "own_data": self.own_data,
            "abstention": self.abstention,
            "conflict": self.conflict,
            "citations": self.citations,
            "provenance": self.provenance,
        }


def _session_with_phase2_fixture() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    scoped = session_factory()
    load_phase2_literature_fixture(scoped)
    scoped.commit()
    return scoped


def _load_cases(path: str | Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _evaluate_retrieval(cases: dict[str, Any]) -> dict[str, Any]:
    gold_path = PROJECT_ROOT / cases.get("retrieval_gold_path", str(DEFAULT_RETRIEVAL_GOLD_PATH))
    benchmark = load_retrieval_benchmark(gold_path)
    session = _session_with_phase2_fixture()
    try:
        metrics = evaluate_retrieval_system(
            session,
            benchmark,
            system_name="bm25_offline",
            retrieval_mode="bm25",
            top_k=10,
        )
    finally:
        session.close()

    return {
        "recall_at_10": metrics.recall_at_10,
        "mrr_at_10": metrics.mrr_at_10,
        "ndcg_at_10": metrics.ndcg_at_10,
        "per_query": metrics.per_query,
        "query_count": len(benchmark.queries),
    }


def _evaluate_taxonomy_safety(cases: dict[str, Any]) -> dict[str, Any]:
    taxonomy_cases = cases.get("taxonomy_cases", [])
    passed = 0
    overclaim_violations = 0
    details: list[dict[str, Any]] = []

    for case in taxonomy_cases:
        result = grade_evidence(
            case["query_taxon"],
            case["literature_taxon"],
            observation_method=case.get("observation_method"),
        )
        distance_ok = result.taxonomy_distance.value == case["expected_distance"]
        tier_ok = result.evidence_tier.value == case["expected_tier"]
        overclaim_ok = True
        if case.get("must_prevent_strain_claim"):
            overclaim_ok = not tier_allows_strain_claim(result.evidence_tier)
            if not overclaim_ok:
                overclaim_violations += 1
        case_pass = distance_ok and tier_ok and overclaim_ok
        passed += int(case_pass)
        details.append(
            {
                "case_id": case["case_id"],
                "passed": case_pass,
                "taxonomy_distance": result.taxonomy_distance.value,
                "evidence_tier": result.evidence_tier.value,
            }
        )

    total = len(taxonomy_cases) or 1
    return {
        "case_pass_rate": passed / total,
        "taxonomy_overclaim_rate": overclaim_violations / total,
        "passed_cases": passed,
        "total_cases": len(taxonomy_cases),
        "details": details,
    }


def _evaluate_linking(cases: dict[str, Any]) -> dict[str, Any]:
    linking_cases = cases.get("linking_cases", [])
    passed = 0
    details: list[dict[str, Any]] = []
    for case in linking_cases:
        matrix = link_natural_product_candidates(
            case["query_taxon"],
            metabolite_name=case.get("metabolite_name"),
        )
        top = matrix.rows[0] if matrix.rows else None
        compound_ok = top is not None and top.compound_name == case["expected_top_compound"]
        tier_ok = top is not None and top.evidence_tier >= case["min_tier"]
        case_pass = compound_ok and tier_ok
        passed += int(case_pass)
        details.append(
            {
                "case_id": case["case_id"],
                "passed": case_pass,
                "top_compound": top.compound_name if top else None,
                "evidence_tier": top.evidence_tier if top else None,
            }
        )
    total = len(linking_cases) or 1
    return {
        "case_pass_rate": passed / total,
        "passed_cases": passed,
        "total_cases": len(linking_cases),
        "details": details,
    }


def _evaluate_own_data() -> dict[str, Any]:
    result = run_own_data_pipeline(PROJECT_ROOT / "data" / "fixtures" / "own_data_demo")
    association_count = len(result.association_results)
    candidate_rows = sum(len(item.candidate_matrix.rows) for item in result.association_results)
    return {
        "association_count": association_count,
        "candidate_rows": candidate_rows,
        "passed": association_count >= 1 and candidate_rows >= 1,
    }


def _evaluate_abstention(cases: dict[str, Any]) -> dict[str, Any]:
    abstention_cases = cases.get("abstention_cases", [])
    passed = 0
    details: list[dict[str, Any]] = []
    for case in abstention_cases:
        answer = write_grounded_answer(
            WriterRequest(question=case["question"], evidence_items=[])
        )
        case_pass = answer.status.value == case["expected_status"]
        passed += int(case_pass)
        details.append(
            {
                "case_id": case["case_id"],
                "passed": case_pass,
                "status": answer.status.value,
            }
        )
    total = len(abstention_cases) or 1
    return {
        "abstention_accuracy": passed / total,
        "passed_cases": passed,
        "total_cases": len(abstention_cases),
        "details": details,
    }


def _evaluate_conflict(cases: dict[str, Any]) -> dict[str, Any]:
    conflict_cases = cases.get("conflict_cases", [])
    passed = 0
    details: list[dict[str, Any]] = []
    for case in conflict_cases:
        support = EvidenceInput(
            evidence_id=uuid.uuid4(),
            claim_type="taxon_produces_compound",
            predicate="PRODUCES",
            object_literal="Rapamycin",
            evidence_tier=case["support_tier"],
            confidence=0.8,
            supporting_span="support",
        )
        conflict = EvidenceInput(
            evidence_id=uuid.uuid4(),
            claim_type="taxon_produces_compound",
            predicate=case["conflict_predicate"],
            object_literal="Rapamycin",
            evidence_tier=case["support_tier"],
            confidence=0.8,
            supporting_span="conflict",
        )
        answer = write_grounded_answer(
            WriterRequest(
                question=case["question"],
                evidence_items=[support, conflict],
            )
        )
        case_pass = answer.status.value == case["expected_status"]
        passed += int(case_pass)
        details.append(
            {
                "case_id": case["case_id"],
                "passed": case_pass,
                "status": answer.status.value,
            }
        )
    total = len(conflict_cases) or 1
    return {
        "conflict_detection_rate": passed / total,
        "passed_cases": passed,
        "total_cases": len(conflict_cases),
        "details": details,
    }


def _evaluate_citations(cases: dict[str, Any]) -> dict[str, Any]:
    citation_cases = cases.get("citation_cases", [])
    coverages: list[float] = []
    validities: list[float] = []
    details: list[dict[str, Any]] = []

    for case in citation_cases:
        evidence_id = uuid.uuid4()
        answer = write_grounded_answer(
            WriterRequest(
                question=case["question"],
                evidence_items=[
                    EvidenceInput(
                        evidence_id=evidence_id,
                        claim_type="taxon_produces_compound",
                        predicate="PRODUCES",
                        object_literal="Rapamycin",
                        evidence_tier=case["evidence_tier"],
                        confidence=0.9,
                        supporting_span="Synthetic span.",
                    )
                ],
            )
        )
        if not answer.claims:
            coverages.append(0.0)
            validities.append(0.0)
            details.append({"case_id": case["case_id"], "citation_coverage": 0.0})
            continue

        claim_refs = [ref for claim in answer.claims for ref in claim.evidence_refs]
        coverage = len(claim_refs) / max(len(answer.claims), 1)
        valid_refs = sum(1 for ref in claim_refs if ref in answer.evidence_refs)
        validity = valid_refs / max(len(claim_refs), 1)
        coverages.append(coverage)
        validities.append(validity)
        details.append(
            {
                "case_id": case["case_id"],
                "citation_coverage": coverage,
                "citation_validity": validity,
            }
        )

    return {
        "citation_coverage": aggregate_metric(coverages),
        "citation_validity": aggregate_metric(validities),
        "details": details,
    }


def run_end_to_end_evaluation(
    cases_path: str | Path = DEFAULT_CASES_PATH,
) -> EndToEndEvalReport:
    cases = _load_cases(cases_path)
    return EndToEndEvalReport(
        benchmark_id=str(cases["benchmark_id"]),
        description=str(cases.get("description", "")),
        retrieval=_evaluate_retrieval(cases),
        taxonomy_safety=_evaluate_taxonomy_safety(cases),
        linking=_evaluate_linking(cases),
        own_data=_evaluate_own_data(),
        abstention=_evaluate_abstention(cases),
        conflict=_evaluate_conflict(cases),
        citations=_evaluate_citations(cases),
        provenance={
            "evaluator": "rhizonp.evaluation.end_to_end",
            "cases_path": str(cases_path),
            "offline": True,
            "fabricated_metrics": False,
        },
    )


def write_evaluation_reports(
    report: EndToEndEvalReport,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "end_to_end_report.json"
    md_path = directory / "end_to_end_report.md"

    payload = report.to_dict()
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# RhizoNP Navigator End-to-End Evaluation Report",
        "",
        f"Benchmark: `{report.benchmark_id}`",
        "",
        report.description,
        "",
        "## Retrieval",
        "",
        f"- Recall@10: {payload['retrieval']['recall_at_10']:.4f}",
        f"- MRR@10: {payload['retrieval']['mrr_at_10']:.4f}",
        f"- nDCG@10: {payload['retrieval']['ndcg_at_10']:.4f}",
        "",
        "## Taxonomy Safety",
        "",
        f"- Case pass rate: {payload['taxonomy_safety']['case_pass_rate']:.4f}",
        f"- Taxonomy overclaim rate: {payload['taxonomy_safety']['taxonomy_overclaim_rate']:.4f}",
        "",
        "## Natural Product Linking",
        "",
        f"- Case pass rate: {payload['linking']['case_pass_rate']:.4f}",
        "",
        "## Own-data-to-literature",
        "",
        f"- Associations processed: {payload['own_data']['association_count']}",
        f"- Candidate rows: {payload['own_data']['candidate_rows']}",
        "",
        "## Abstention",
        "",
        f"- Abstention accuracy: {payload['abstention']['abstention_accuracy']:.4f}",
        "",
        "## Conflicting Evidence",
        "",
        f"- Conflict detection rate: {payload['conflict']['conflict_detection_rate']:.4f}",
        "",
        "## Citations",
        "",
        f"- Citation coverage: {payload['citations']['citation_coverage']:.4f}",
        f"- Citation validity: {payload['citations']['citation_validity']:.4f}",
        "",
        "## Provenance",
        "",
        "- Offline deterministic fixtures only.",
        "- No fabricated benchmark improvements.",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path
