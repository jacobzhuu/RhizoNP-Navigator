from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class QueryRecord:
    query_id: str
    text: str
    source: str


@dataclass(frozen=True)
class PairComparison:
    corpus_query_id: str
    benchmark_query_id: str
    corpus_text: str
    benchmark_text: str
    exact_match: bool
    normalized_match: bool
    token_jaccard: float
    sequence_similarity: float
    shared_tokens: tuple[str, ...]
    flags: tuple[str, ...]


@dataclass(frozen=True)
class LeakageAuditReport:
    corpus_query_count: int
    benchmark_query_count: int
    comparisons: tuple[PairComparison, ...]
    exact_duplicates: tuple[PairComparison, ...]
    normalized_duplicates: tuple[PairComparison, ...]
    high_token_overlap: tuple[PairComparison, ...]
    high_sequence_similarity: tuple[PairComparison, ...]


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.casefold()))


def normalize_query_text(text: str) -> str:
    lowered = text.casefold()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def token_jaccard(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return len(intersection) / len(union)


def sequence_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_query_text(left), normalize_query_text(right)).ratio()


def load_corpus_queries(path: str | Path) -> list[QueryRecord]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records: list[QueryRecord] = []
    for entry in payload.get("queries", []):
        records.append(
            QueryRecord(
                query_id=str(entry["query_id"]),
                text=str(entry.get("term") or entry.get("query") or ""),
                source="corpus",
            )
        )
    return records


def load_benchmark_queries(path: str | Path) -> list[QueryRecord]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records: list[QueryRecord] = []
    for entry in payload.get("queries", []):
        records.append(
            QueryRecord(
                query_id=str(entry["query_id"]),
                text=str(entry.get("query") or entry.get("term") or ""),
                source="benchmark",
            )
        )
    return records


def _comparison_flags(
    *,
    exact_match: bool,
    normalized_match: bool,
    token_jaccard_value: float,
    sequence_similarity_value: float,
    token_overlap_threshold: float,
    sequence_similarity_threshold: float,
) -> tuple[str, ...]:
    flags: list[str] = []
    if exact_match:
        flags.append("exact_duplicate")
    if normalized_match:
        flags.append("normalized_duplicate")
    if token_jaccard_value >= token_overlap_threshold:
        flags.append("high_token_overlap")
    if sequence_similarity_value >= sequence_similarity_threshold:
        flags.append("high_sequence_similarity")
    return tuple(flags)


def compare_query_sets(
    corpus_queries: Sequence[QueryRecord],
    benchmark_queries: Sequence[QueryRecord],
    *,
    token_overlap_threshold: float = 0.6,
    sequence_similarity_threshold: float = 0.75,
) -> LeakageAuditReport:
    comparisons: list[PairComparison] = []
    for corpus_query in corpus_queries:
        for benchmark_query in benchmark_queries:
            exact_match = corpus_query.text.strip() == benchmark_query.text.strip()
            normalized_match = normalize_query_text(corpus_query.text) == normalize_query_text(
                benchmark_query.text
            )
            jaccard = token_jaccard(corpus_query.text, benchmark_query.text)
            similarity = sequence_similarity(corpus_query.text, benchmark_query.text)
            shared = tuple(sorted(_tokenize(corpus_query.text) & _tokenize(benchmark_query.text)))
            flags = _comparison_flags(
                exact_match=exact_match,
                normalized_match=normalized_match,
                token_jaccard_value=jaccard,
                sequence_similarity_value=similarity,
                token_overlap_threshold=token_overlap_threshold,
                sequence_similarity_threshold=sequence_similarity_threshold,
            )
            comparisons.append(
                PairComparison(
                    corpus_query_id=corpus_query.query_id,
                    benchmark_query_id=benchmark_query.query_id,
                    corpus_text=corpus_query.text,
                    benchmark_text=benchmark_query.text,
                    exact_match=exact_match,
                    normalized_match=normalized_match,
                    token_jaccard=jaccard,
                    sequence_similarity=similarity,
                    shared_tokens=shared,
                    flags=flags,
                )
            )

    def _filter(flag: str) -> tuple[PairComparison, ...]:
        return tuple(comparison for comparison in comparisons if flag in comparison.flags)

    return LeakageAuditReport(
        corpus_query_count=len(corpus_queries),
        benchmark_query_count=len(benchmark_queries),
        comparisons=tuple(comparisons),
        exact_duplicates=_filter("exact_duplicate"),
        normalized_duplicates=_filter("normalized_duplicate"),
        high_token_overlap=_filter("high_token_overlap"),
        high_sequence_similarity=_filter("high_sequence_similarity"),
    )


def audit_report_to_dict(report: LeakageAuditReport) -> dict[str, Any]:
    def _pair_dict(comparison: PairComparison) -> dict[str, Any]:
        return {
            "corpus_query_id": comparison.corpus_query_id,
            "benchmark_query_id": comparison.benchmark_query_id,
            "corpus_text": comparison.corpus_text,
            "benchmark_text": comparison.benchmark_text,
            "exact_match": comparison.exact_match,
            "normalized_match": comparison.normalized_match,
            "token_jaccard": comparison.token_jaccard,
            "sequence_similarity": comparison.sequence_similarity,
            "shared_tokens": list(comparison.shared_tokens),
            "flags": list(comparison.flags),
            "review_status": "automatic_lexical_warning_only",
        }

    flagged = [
        _pair_dict(comparison)
        for comparison in report.comparisons
        if comparison.flags
    ]
    return {
        "audit_type": "corpus_benchmark_query_leakage",
        "corpus_query_count": report.corpus_query_count,
        "benchmark_query_count": report.benchmark_query_count,
        "pair_count": len(report.comparisons),
        "summary": {
            "exact_duplicates": len(report.exact_duplicates),
            "normalized_duplicates": len(report.normalized_duplicates),
            "high_token_overlap": len(report.high_token_overlap),
            "high_sequence_similarity": len(report.high_sequence_similarity),
            "flagged_pairs": len(flagged),
        },
        "methodology": {
            "exact_match": "Raw string equality after strip().",
            "normalized_match": "Lowercase alphanumeric token stream equality.",
            "token_jaccard": "Intersection over union of [a-z0-9]+ tokens.",
            "sequence_similarity": "difflib.SequenceMatcher ratio on normalized strings.",
            "human_review_required": (
                "Automatic flags are lexical warnings only; they do not prove benchmark leakage."
            ),
        },
        "flagged_pairs": flagged,
    }


def audit_report_to_markdown(report: LeakageAuditReport) -> str:
    lines = [
        "# Corpus / Benchmark Query Leakage Audit",
        "",
        "Automatic lexical comparison only. Flagged pairs require human review before "
        "any leakage conclusion.",
        "",
        "## Summary",
        "",
        f"- Corpus queries: {report.corpus_query_count}",
        f"- Benchmark queries: {report.benchmark_query_count}",
        f"- Exact duplicates: {len(report.exact_duplicates)}",
        f"- Normalized duplicates: {len(report.normalized_duplicates)}",
        f"- High token overlap: {len(report.high_token_overlap)}",
        f"- High sequence similarity: {len(report.high_sequence_similarity)}",
        "",
        "## Flagged Pairs",
        "",
    ]
    flagged = [comparison for comparison in report.comparisons if comparison.flags]
    if not flagged:
        lines.append("No lexical warnings detected.")
        return "\n".join(lines) + "\n"

    for comparison in flagged:
        lines.extend(
            [
                f"### {comparison.corpus_query_id} ↔ {comparison.benchmark_query_id}",
                "",
                f"- Corpus: `{comparison.corpus_text}`",
                f"- Benchmark: `{comparison.benchmark_text}`",
                f"- Flags: {', '.join(comparison.flags)}",
                f"- Token Jaccard: {comparison.token_jaccard:.3f}",
                f"- Sequence similarity: {comparison.sequence_similarity:.3f}",
                f"- Shared tokens: {', '.join(comparison.shared_tokens) if comparison.shared_tokens else '(none)'}",
                "- Review status: automatic lexical warning only",
                "",
            ]
        )
    return "\n".join(lines)


def run_leakage_audit(
    corpus_queries_path: str | Path,
    benchmark_queries_path: str | Path,
    *,
    token_overlap_threshold: float = 0.6,
    sequence_similarity_threshold: float = 0.75,
) -> LeakageAuditReport:
    corpus_queries = load_corpus_queries(corpus_queries_path)
    benchmark_queries = load_benchmark_queries(benchmark_queries_path)
    return compare_query_sets(
        corpus_queries,
        benchmark_queries,
        token_overlap_threshold=token_overlap_threshold,
        sequence_similarity_threshold=sequence_similarity_threshold,
    )


def write_leakage_audit_reports(
    report: LeakageAuditReport,
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    json_output = Path(json_path)
    markdown_output = Path(markdown_path)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(audit_report_to_dict(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_output.write_text(audit_report_to_markdown(report), encoding="utf-8")
    return json_output, markdown_output
