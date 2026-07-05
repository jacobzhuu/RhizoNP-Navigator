"""Retrieval evaluation utilities for Phase 2 benchmarks."""

from rhizonp.evaluation.annotation import (
    AnnotationCandidate,
    AnnotationImportResult,
    export_annotation_candidates,
    import_annotation_labels,
    validate_imported_labels,
    write_annotation_export_csv,
)
from rhizonp.evaluation.real_benchmark import (
    RealBenchmarkReport,
    RealBenchmarkSpec,
    aggregate_results_to_papers,
    benchmark_annotation_status,
    load_real_benchmark,
    real_benchmark_report_to_dict,
    run_real_retrieval_benchmark,
)
from rhizonp.evaluation.retrieval_benchmark import (
    RetrievalBenchmarkReport,
    RetrievalBenchmarkSpec,
    RetrievalQueryGold,
    SystemRetrievalMetrics,
    benchmark_report_to_dict,
    evaluate_retrieval_system,
    load_retrieval_benchmark,
    run_retrieval_benchmark,
)
from rhizonp.evaluation.retrieval_metrics import (
    aggregate_metric,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)

__all__ = [
    "AnnotationCandidate",
    "AnnotationImportResult",
    "RealBenchmarkReport",
    "RealBenchmarkSpec",
    "RetrievalBenchmarkReport",
    "RetrievalBenchmarkSpec",
    "RetrievalQueryGold",
    "SystemRetrievalMetrics",
    "aggregate_metric",
    "aggregate_results_to_papers",
    "benchmark_annotation_status",
    "benchmark_report_to_dict",
    "evaluate_retrieval_system",
    "export_annotation_candidates",
    "import_annotation_labels",
    "load_real_benchmark",
    "load_retrieval_benchmark",
    "mrr_at_k",
    "ndcg_at_k",
    "real_benchmark_report_to_dict",
    "recall_at_k",
    "reciprocal_rank",
    "run_real_retrieval_benchmark",
    "run_retrieval_benchmark",
    "validate_imported_labels",
    "write_annotation_export_csv",
]
