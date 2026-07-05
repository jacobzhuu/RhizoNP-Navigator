from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT
from rhizonp.writer.citation_validation import validate_citation_trace
from rhizonp.writer.claim_safety import (
    check_forbidden_claim_patterns,
    classify_overclaim_violations,
)
from rhizonp.writer.faithfulness import evaluate_claim_faithfulness_diagnostics
from rhizonp.writer.models import AnswerStatus, EvidenceInput, WriterRequest
from rhizonp.writer.service import write_grounded_answer

DEFAULT_CASES_PATH = PROJECT_ROOT / "data" / "eval" / "writer_safety_cases.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "eval" / "reports" / "latest"


@dataclass(frozen=True)
class WriterSafetyCaseResult:
    case_id: str
    category: str
    passed: bool
    expected_status: str
    actual_status: str
    forbidden_violations: list[str]
    missing_required_limitations: list[str]
    citation_ref_validity_rate: float
    citation_provenance_coverage: float
    evidence_trace_completeness: float
    unsupported_claim_rate: float
    expected_abstention: bool | None
    expected_conflict: bool | None
    abstention_correct: bool | None
    conflict_correct: bool | None
    bounded_answer_correct: bool | None
    overclaim_reports: dict[str, Any]
    faithfulness_diagnostics: list[dict[str, Any]]
    provenance_scope: str
    notes: str
    source_trace: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "passed": self.passed,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "forbidden_violations": list(self.forbidden_violations),
            "missing_required_limitations": list(self.missing_required_limitations),
            "citation_ref_validity_rate": self.citation_ref_validity_rate,
            "citation_provenance_coverage": self.citation_provenance_coverage,
            "evidence_trace_completeness": self.evidence_trace_completeness,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "expected_abstention": self.expected_abstention,
            "expected_conflict": self.expected_conflict,
            "abstention_correct": self.abstention_correct,
            "conflict_correct": self.conflict_correct,
            "bounded_answer_correct": self.bounded_answer_correct,
            "overclaim_reports": dict(self.overclaim_reports),
            "faithfulness_diagnostics": list(self.faithfulness_diagnostics),
            "provenance_scope": self.provenance_scope,
            "notes": self.notes,
            "source_trace": dict(self.source_trace),
            "issues": list(self.issues),
        }


@dataclass(frozen=True)
class WriterSafetyBenchmarkReport:
    benchmark_id: str
    description: str
    disclaimer: str
    case_count: int
    category_distribution: dict[str, int]
    passed_count: int
    failed_count: int
    must_abstain_accuracy: float
    must_conflict_accuracy: float
    bounded_answer_accuracy: float
    forbidden_claim_violation_rate: float
    unsupported_claim_rate: float
    taxonomy_overclaim_rate: float
    chemical_identity_overclaim_rate: float
    causality_overclaim_rate: float
    citation_ref_validity_rate: float
    citation_provenance_coverage: float
    evidence_trace_completeness: float
    heuristic_faithfulness_pending: bool
    human_faithfulness_pending: bool
    case_results: list[WriterSafetyCaseResult]
    dynamic_results: list[WriterSafetyCaseResult] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "description": self.description,
            "disclaimer": self.disclaimer,
            "case_count": self.case_count,
            "category_distribution": dict(self.category_distribution),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "must_abstain_accuracy": self.must_abstain_accuracy,
            "must_conflict_accuracy": self.must_conflict_accuracy,
            "bounded_answer_accuracy": self.bounded_answer_accuracy,
            "forbidden_claim_violation_rate": self.forbidden_claim_violation_rate,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "taxonomy_overclaim_rate": self.taxonomy_overclaim_rate,
            "chemical_identity_overclaim_rate": self.chemical_identity_overclaim_rate,
            "causality_overclaim_rate": self.causality_overclaim_rate,
            "citation_ref_validity_rate": self.citation_ref_validity_rate,
            "citation_provenance_coverage": self.citation_provenance_coverage,
            "evidence_trace_completeness": self.evidence_trace_completeness,
            "heuristic_faithfulness_pending": self.heuristic_faithfulness_pending,
            "human_faithfulness_pending": self.human_faithfulness_pending,
            "case_results": [item.to_dict() for item in self.case_results],
            "dynamic_results": [item.to_dict() for item in self.dynamic_results],
            "limitations": list(self.limitations),
            "passed": self.failed_count == 0,
        }


def load_writer_safety_cases(path: str | Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_evidence_items(raw_items: list[dict[str, Any]]) -> list[EvidenceInput]:
    items: list[EvidenceInput] = []
    for raw in raw_items:
        payload = dict(raw)
        if "evidence_id" in payload:
            payload["evidence_id"] = uuid.UUID(str(payload["evidence_id"]))
        items.append(EvidenceInput(**payload))
    return items


def _missing_required_limitations(answer_text: str, limitations: list[str], required: list[str]) -> list[str]:
    combined = f"{answer_text}\n" + "\n".join(limitations)
    lowered = combined.lower()
    missing: list[str] = []
    for item in required:
        if item.lower() not in lowered:
            missing.append(item)
    return missing


def evaluate_static_case(case: dict[str, Any]) -> WriterSafetyCaseResult:
    evidence_items = _parse_evidence_items(list(case.get("evidence_items") or []))
    request = WriterRequest(
        question=str(case["question"]),
        evidence_items=evidence_items,
        taxonomy_warnings=list(case.get("taxonomy_warnings") or []),
        limitations=list(case.get("limitations") or []),
    )
    answer = write_grounded_answer(request)
    validation = validate_citation_trace(evidence_items, answer)
    forbidden = check_forbidden_claim_patterns(
        answer,
        list(case.get("forbidden_claim_patterns") or []),
    )
    overclaim_reports = {
        key: report.to_dict() for key, report in classify_overclaim_violations(answer).items()
    }
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    faithfulness = evaluate_claim_faithfulness_diagnostics(answer.claims, evidence_by_id)

    expected_status = str(case["expected_status"])
    actual_status = answer.status.value
    expected_abstention = case.get("expected_abstention")
    expected_conflict = case.get("expected_conflict")

    abstention_correct = None
    if expected_abstention is True:
        abstention_correct = actual_status == AnswerStatus.INSUFFICIENT_EVIDENCE.value
    elif expected_abstention is False:
        abstention_correct = actual_status != AnswerStatus.INSUFFICIENT_EVIDENCE.value

    conflict_correct = None
    if expected_conflict is True:
        conflict_correct = actual_status == AnswerStatus.CONFLICTING_EVIDENCE.value
    elif expected_conflict is False:
        conflict_correct = actual_status != AnswerStatus.CONFLICTING_EVIDENCE.value

    category = str(case.get("category") or "unknown")
    bounded_answer_correct = None
    if category.startswith("bounded_answer") or category in {"mention_only", "fixture_only"}:
        bounded_answer_correct = actual_status == expected_status and not forbidden.violations

    missing_required = _missing_required_limitations(
        answer.answer,
        answer.limitations,
        list(case.get("required_limitations") or []),
    )
    unsupported_rate = (
        validation.unsupported_claim_count / len(answer.claims) if answer.claims else 0.0
    )

    issues: list[str] = []
    if actual_status != expected_status:
        issues.append(f"status mismatch: expected {expected_status}, got {actual_status}")
    issues.extend(forbidden.violations)
    issues.extend(f"missing limitation: {item}" for item in missing_required)

    min_validity = case.get("min_citation_ref_validity_rate")
    if min_validity is not None and validation.citation_ref_validity_rate < float(min_validity):
        issues.append("citation_ref_validity_rate below minimum")
    max_provenance = case.get("max_citation_provenance_coverage")
    if max_provenance is not None and validation.citation_provenance_coverage > float(max_provenance):
        issues.append("citation_provenance_coverage above maximum")
    min_trace = case.get("min_evidence_trace_completeness")
    if min_trace is not None and validation.evidence_trace_completeness < float(min_trace):
        issues.append("evidence_trace_completeness below minimum")

    if expected_abstention is True and not abstention_correct:
        issues.append("must-abstain case did not abstain")
    if expected_conflict is True and not conflict_correct:
        issues.append("must-conflict case did not report conflict")
    if expected_conflict is False and conflict_correct is False:
        issues.append("false conflict detected")

    return WriterSafetyCaseResult(
        case_id=str(case["case_id"]),
        category=category,
        passed=not issues,
        expected_status=expected_status,
        actual_status=actual_status,
        forbidden_violations=forbidden.violations,
        missing_required_limitations=missing_required,
        citation_ref_validity_rate=validation.citation_ref_validity_rate,
        citation_provenance_coverage=validation.citation_provenance_coverage,
        evidence_trace_completeness=validation.evidence_trace_completeness,
        unsupported_claim_rate=round(unsupported_rate, 4),
        expected_abstention=expected_abstention,
        expected_conflict=expected_conflict,
        abstention_correct=abstention_correct,
        conflict_correct=conflict_correct,
        bounded_answer_correct=bounded_answer_correct,
        overclaim_reports=overclaim_reports,
        faithfulness_diagnostics=faithfulness,
        provenance_scope=str(case.get("provenance_scope") or "synthetic"),
        notes=str(case.get("notes") or ""),
        issues=issues,
    )


def run_real_pubmed_dynamic_case() -> WriterSafetyCaseResult | None:
    from rhizonp.domain.models import Base
    from rhizonp.omics.real_pubmed_validation import (
        DEFAULT_SNAPSHOT_DIR,
        create_validation_engine,
        ingest_bounded_pubmed_snapshot,
    )
    from rhizonp.storage.postgres import create_session_factory
    from rhizonp.writer.citation_validation import resolve_evidence_trace
    from rhizonp.writer.retrieval_service import retrieve_literature_evidence_hits
    from rhizonp.writer.retrieval_writer import write_grounded_answer_from_literature_hits

    snapshot_path = DEFAULT_SNAPSHOT_DIR / "corpus.json"
    if not snapshot_path.is_file():
        return None

    engine = create_validation_engine()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        ingest_bounded_pubmed_snapshot(session, snapshot_path)
        query = "Streptomyces microbial natural products"
        hits = retrieve_literature_evidence_hits(
            session,
            query,
            query_taxon="Streptomyces",
            observation_method="synthetic_16S_fixture",
            retrieval_mode="bm25",
            top_k=2,
        )
        writer_result = write_grounded_answer_from_literature_hits(
            f"What literature mentions: {query}?",
            hits,
            limitations=["Real bounded PubMed mention does not imply production or causation."],
            retrieval_status="RETRIEVED" if hits else "NO_RESULTS",
        )
        answer = writer_result.answer
        forbidden = check_forbidden_claim_patterns(
            answer,
            ["confirmed production", "this sample produces", " causes "],
        )
        top_evidence = writer_result.evidence_items[0] if writer_result.evidence_items else None
        trace = resolve_evidence_trace(top_evidence) if top_evidence else {}
        top_hit = hits[0].to_dict() if hits else {}
        issues: list[str] = []
        if not hits:
            issues.append("no real PubMed hits returned")
        if forbidden.violations:
            issues.extend(forbidden.violations)
        if top_evidence is None or not trace.get("pmid"):
            issues.append("missing real PMID trace")
        expected_status = (
            AnswerStatus.PARTIALLY_SUPPORTED.value
            if answer.status != AnswerStatus.INSUFFICIENT_EVIDENCE
            else AnswerStatus.INSUFFICIENT_EVIDENCE.value
        )
        return WriterSafetyCaseResult(
            case_id="DYN_PUBMED001",
            category="real_bounded_pubmed",
            passed=not issues,
            expected_status=expected_status,
            actual_status=answer.status.value,
            forbidden_violations=forbidden.violations,
            missing_required_limitations=[],
            citation_ref_validity_rate=writer_result.citation_validation.citation_ref_validity_rate,
            citation_provenance_coverage=writer_result.citation_validation.citation_provenance_coverage,
            evidence_trace_completeness=writer_result.citation_validation.evidence_trace_completeness,
            unsupported_claim_rate=writer_result.citation_validation.unsupported_claim_count,
            expected_abstention=False,
            expected_conflict=False,
            abstention_correct=answer.status != AnswerStatus.INSUFFICIENT_EVIDENCE,
            conflict_correct=True,
            bounded_answer_correct=not forbidden.violations,
            overclaim_reports={
                key: report.to_dict()
                for key, report in classify_overclaim_violations(answer).items()
            },
            faithfulness_diagnostics=writer_result.faithfulness_diagnostics,
            provenance_scope="real_bounded_pubmed",
            notes="Real bounded PubMed retrieval mention must remain bounded; trace required.",
            source_trace={
                "query": query,
                "retrieval_mode": "bm25",
                "chunk_id": top_hit.get("chunk_id"),
                "paper_id": top_hit.get("paper_id"),
                "pmid": top_hit.get("pmid"),
                "doi": top_hit.get("doi"),
                "source_url": top_hit.get("source_url"),
                "evidence_id": trace.get("evidence_id"),
            },
            issues=issues,
        )
    finally:
        session.close()


def run_own_data_feature_m123_dynamic_case() -> WriterSafetyCaseResult:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from rhizonp.domain.models import Base
    from rhizonp.ingestion.literature import load_phase2_literature_fixture
    from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
    from rhizonp.storage.postgres import create_session_factory

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
    try:
        result = run_own_data_pipeline(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
            session=session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=True,
                enable_grounded_writer=True,
            ),
        )
        assoc = next(
            item
            for item in result.association_results
            if item.metabolite.raw_label == "Feature_M123"
        )
        writer_payload = assoc.grounded_writer or {}
        answer_payload = writer_payload.get("answer") or {}
        actual_status = str(answer_payload.get("status") or AnswerStatus.INSUFFICIENT_EVIDENCE.value)
        claims = answer_payload.get("claims") or []
        combined_text = answer_payload.get("answer", "") + " " + " ".join(
            str(claim.get("text", "")) for claim in claims
        )
        forbidden_patterns = [
            "Feature_M123 is",
            "confirmed as",
            " causes ",
            "this sample produces",
            "detected strain",
        ]
        forbidden_violations = [
            pattern
            for pattern in forbidden_patterns
            if pattern.lower() in combined_text.lower()
        ]
        limitations = answer_payload.get("limitations") or []
        missing = _missing_required_limitations(
            answer_payload.get("answer", ""),
            [str(item) for item in limitations],
            ["Correlation or co-occurrence does not imply biochemical production or causation."],
        )
        lit = assoc.literature_retrieval
        top_hit = (lit.get("hits") or [{}])[0]
        issues: list[str] = []
        if forbidden_violations:
            issues.extend(f"forbidden pattern: {item}" for item in forbidden_violations)
        if missing:
            issues.extend(f"missing limitation: {item}" for item in missing)
        if "Feature_M123" in combined_text and "rapamycin" in combined_text.lower():
            issues.append("Feature_M123 must not be equated to a confirmed compound")
        return WriterSafetyCaseResult(
            case_id="DYN_OWN001",
            category="own_data_feature_m123",
            passed=not issues,
            expected_status=AnswerStatus.PARTIALLY_SUPPORTED.value,
            actual_status=actual_status,
            forbidden_violations=forbidden_violations,
            missing_required_limitations=missing,
            citation_ref_validity_rate=float(
                (writer_payload.get("citation_validation") or {}).get(
                    "citation_ref_validity_rate",
                    0.0,
                )
            ),
            citation_provenance_coverage=float(
                (writer_payload.get("citation_validation") or {}).get(
                    "citation_provenance_coverage",
                    0.0,
                )
            ),
            evidence_trace_completeness=float(
                (writer_payload.get("citation_validation") or {}).get(
                    "evidence_trace_completeness",
                    0.0,
                )
            ),
            unsupported_claim_rate=0.0,
            expected_abstention=False,
            expected_conflict=False,
            abstention_correct=actual_status != AnswerStatus.INSUFFICIENT_EVIDENCE.value,
            conflict_correct=True,
            bounded_answer_correct=not forbidden_violations,
            overclaim_reports={},
            faithfulness_diagnostics=list(writer_payload.get("faithfulness_diagnostics") or []),
            provenance_scope="fixture_literature",
            notes="Own-data Streptomyces ↔ Feature_M123 must remain unknown and non-causal.",
            source_trace={
                "association_id": assoc.association.association_id,
                "source_raw_label": assoc.association.source_raw_label,
                "target_raw_label": assoc.association.target_raw_label,
                "query_text": top_hit.get("query_text"),
                "retrieval_mode": top_hit.get("retrieval_mode"),
                "chunk_id": top_hit.get("chunk_id"),
                "paper_id": top_hit.get("paper_id"),
                "pmid": top_hit.get("pmid"),
            },
            issues=issues,
        )
    finally:
        session.close()


def _accuracy(values: list[bool | None]) -> float:
    filtered = [item for item in values if item is not None]
    if not filtered:
        return 1.0
    return round(sum(1 for item in filtered if item) / len(filtered), 4)


def _mean(values: list[float]) -> float:
    if not values:
        return 1.0
    return round(sum(values) / len(values), 4)


def run_writer_safety_benchmark(
    *,
    cases_path: str | Path = DEFAULT_CASES_PATH,
    include_dynamic: bool = True,
) -> WriterSafetyBenchmarkReport:
    payload = load_writer_safety_cases(cases_path)
    static_results = [evaluate_static_case(case) for case in payload.get("cases", [])]
    dynamic_results: list[WriterSafetyCaseResult] = []
    if include_dynamic:
        own_data_result = run_own_data_feature_m123_dynamic_case()
        dynamic_results.append(own_data_result)
        pubmed_result = run_real_pubmed_dynamic_case()
        if pubmed_result is not None:
            dynamic_results.append(pubmed_result)

    all_results = static_results + dynamic_results
    category_distribution = dict(Counter(item.category for item in all_results))
    passed_count = sum(1 for item in all_results if item.passed)
    failed_count = len(all_results) - passed_count

    abstain_cases = [item for item in all_results if item.expected_abstention is True]
    conflict_cases = [item for item in all_results if item.expected_conflict is True]
    bounded_cases = [
        item
        for item in all_results
        if item.category.startswith("bounded_answer")
        or item.category in {"mention_only", "fixture_only", "real_bounded_pubmed", "own_data_feature_m123"}
    ]

    forbidden_rate = _mean([1.0 if item.forbidden_violations else 0.0 for item in all_results])
    overclaim_taxonomy = _mean(
        [
            1.0 if (item.overclaim_reports.get("taxonomy_overclaim") or {}).get("violation_count") else 0.0
            for item in all_results
            if item.overclaim_reports
        ]
    )
    overclaim_chemical = _mean(
        [
            1.0
            if (item.overclaim_reports.get("chemical_identity_overclaim") or {}).get("violation_count")
            else 0.0
            for item in all_results
            if item.overclaim_reports
        ]
    )
    overclaim_causality = _mean(
        [
            1.0 if (item.overclaim_reports.get("causality_overclaim") or {}).get("violation_count") else 0.0
            for item in all_results
            if item.overclaim_reports
        ]
    )

    return WriterSafetyBenchmarkReport(
        benchmark_id=str(payload.get("benchmark_id") or "writer_safety_v1"),
        description=str(payload.get("description") or ""),
        disclaimer=str(payload.get("disclaimer") or ""),
        case_count=len(all_results),
        category_distribution=category_distribution,
        passed_count=passed_count,
        failed_count=failed_count,
        must_abstain_accuracy=_accuracy([item.abstention_correct for item in abstain_cases]),
        must_conflict_accuracy=_accuracy([item.conflict_correct for item in conflict_cases]),
        bounded_answer_accuracy=_accuracy([item.bounded_answer_correct for item in bounded_cases]),
        forbidden_claim_violation_rate=forbidden_rate,
        unsupported_claim_rate=_mean([item.unsupported_claim_rate for item in all_results]),
        taxonomy_overclaim_rate=overclaim_taxonomy,
        chemical_identity_overclaim_rate=overclaim_chemical,
        causality_overclaim_rate=overclaim_causality,
        citation_ref_validity_rate=_mean([item.citation_ref_validity_rate for item in all_results]),
        citation_provenance_coverage=_mean(
            [item.citation_provenance_coverage for item in all_results]
        ),
        evidence_trace_completeness=_mean(
            [item.evidence_trace_completeness for item in all_results]
        ),
        heuristic_faithfulness_pending=True,
        human_faithfulness_pending=True,
        case_results=static_results,
        dynamic_results=dynamic_results,
        limitations=[
            "Deterministic safety/regression benchmark only.",
            "Heuristic forbidden-claim checks are conservative diagnostics, not semantic completeness.",
            "Passing this benchmark does not constitute human scientific validation.",
            "Citation validity is structural; citation faithfulness remains human_faithfulness_pending.",
        ],
    )


def write_writer_safety_reports(
    report: WriterSafetyBenchmarkReport,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "writer_safety_benchmark.json"
    md_path = directory / "writer_safety_benchmark.md"
    payload = report.to_dict()
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Writer Safety Benchmark Report",
        "",
        report.disclaimer,
        "",
        "## Scope",
        "",
        f"- Benchmark ID: `{report.benchmark_id}`",
        f"- Description: {report.description}",
        f"- Case count: **{report.case_count}**",
        f"- Passed: **{report.passed_count}**",
        f"- Failed: **{report.failed_count}**",
        "",
        "## Category distribution",
        "",
    ]
    for category, count in sorted(report.category_distribution.items()):
        lines.append(f"- `{category}`: {count}")
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"- must_abstain_accuracy: **{report.must_abstain_accuracy:.4f}**",
            f"- must_conflict_accuracy: **{report.must_conflict_accuracy:.4f}**",
            f"- bounded_answer_accuracy: **{report.bounded_answer_accuracy:.4f}**",
            f"- forbidden_claim_violation_rate: **{report.forbidden_claim_violation_rate:.4f}**",
            f"- unsupported_claim_rate: **{report.unsupported_claim_rate:.4f}**",
            f"- taxonomy_overclaim_rate: **{report.taxonomy_overclaim_rate:.4f}**",
            f"- chemical_identity_overclaim_rate: **{report.chemical_identity_overclaim_rate:.4f}**",
            f"- causality_overclaim_rate: **{report.causality_overclaim_rate:.4f}**",
            f"- citation_ref_validity_rate: **{report.citation_ref_validity_rate:.4f}**",
            f"- citation_provenance_coverage: **{report.citation_provenance_coverage:.4f}**",
            f"- evidence_trace_completeness: **{report.evidence_trace_completeness:.4f}**",
            f"- heuristic_faithfulness_pending: **{report.heuristic_faithfulness_pending}**",
            f"- human_faithfulness_pending: **{report.human_faithfulness_pending}**",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report.limitations)
    if report.failed_count:
        lines.extend(["", "## Failed cases", ""])
        for item in report.case_results + report.dynamic_results:
            if not item.passed:
                lines.append(f"- `{item.case_id}` ({item.category}): {', '.join(item.issues)}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
