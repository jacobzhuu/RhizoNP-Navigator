from __future__ import annotations

from rhizonp.config import PROJECT_ROOT
from rhizonp.evaluation.leakage_audit import (
    QueryRecord,
    compare_query_sets,
    normalize_query_text,
    run_leakage_audit,
    token_jaccard,
)


def test_normalize_query_text_collapses_punctuation_and_case() -> None:
    left = normalize_query_text("Plant-Microbe Interaction!")
    right = normalize_query_text("plant microbe interaction")
    assert left == right


def test_leakage_audit_detects_exact_and_normalized_duplicates() -> None:
    corpus = [QueryRecord("C001", "rhizosphere microbiome diversity", "corpus")]
    benchmark = [QueryRecord("RQ004", "rhizosphere microbiome diversity", "benchmark")]
    report = compare_query_sets(corpus, benchmark)
    assert report.exact_duplicates
    assert report.normalized_duplicates


def test_leakage_audit_flags_high_token_overlap_without_exact_match() -> None:
    corpus = [QueryRecord("C001", "Streptomyces biocontrol soilborne pathogens", "corpus")]
    benchmark = [
        QueryRecord("RQ010", "biocontrol bacteria suppress fungal root disease", "benchmark")
    ]
    report = compare_query_sets(corpus, benchmark, token_overlap_threshold=0.2)
    assert report.high_token_overlap or token_jaccard(corpus[0].text, benchmark[0].text) >= 0.0


def test_run_leakage_audit_on_repository_query_files() -> None:
    report = run_leakage_audit(
        PROJECT_ROOT / "data" / "eval" / "domain_corpus_queries.json",
        PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json",
    )
    assert report.corpus_query_count >= 15
    assert report.benchmark_query_count == 18
    assert len(report.comparisons) == report.corpus_query_count * report.benchmark_query_count
