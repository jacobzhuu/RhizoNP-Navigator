#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.evaluation.writer_metrics import evaluate_retrieval_grounded_writer_result
    from rhizonp.omics.corpus_provenance import CorpusType
    from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
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
        raise SystemExit(f"Missing bounded PubMed snapshot: {snapshot_path}")

    engine = create_validation_engine()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        ingest_summary, corpus_type, corpus_id = ingest_bounded_pubmed_snapshot(
            session,
            snapshot_path,
        )
        query = "Streptomyces microbial natural products"
        hits = retrieve_literature_evidence_hits(
            session,
            query,
            query_taxon="Streptomyces",
            observation_method="synthetic_16S_fixture",
            retrieval_mode="bm25",
            top_k=3,
        )
        writer_result = write_grounded_answer_from_literature_hits(
            f"What literature relates to: {query}?",
            hits,
            retrieval_status="RETRIEVED" if hits else "NO_RESULTS",
        )
        metrics = evaluate_retrieval_grounded_writer_result(writer_result)

        pipeline_result = run_own_data_pipeline(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
            session=session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=True,
                enable_grounded_writer=True,
                corpus_id=corpus_id,
                corpus_type=corpus_type.value,
            ),
        )
        bridge_writer = (
            pipeline_result.association_results[0].grounded_writer
            if pipeline_result.association_results
            else None
        )

        top_hit = hits[0] if hits else None
        top_evidence = writer_result.evidence_items[0] if writer_result.evidence_items else None
        trace = resolve_evidence_trace(top_evidence) if top_evidence else {}
        report = {
            "validation_type": "retrieval_grounded_writer",
            "corpus": ingest_summary.to_dict(),
            "direct_writer": {
                "query": query,
                "retrieval_mode": "bm25",
                "hit_count": len(hits),
                "top_hit": top_hit.to_dict() if top_hit else None,
                "writer_status": writer_result.answer.status.value,
                "citation_validation": writer_result.citation_validation.to_dict(),
                "metrics": metrics.to_dict(),
                "source_trace": trace,
            },
            "own_data_bridge_writer": bridge_writer,
            "real_trace_present": bool(
                top_hit
                and top_hit.pmid
                and trace.get("chunk_id")
                and trace.get("paper_id")
                and corpus_type == CorpusType.REAL_BOUNDED_PUBMED
            ),
            "passed": bool(
                hits
                and writer_result.citation_validation.citation_ref_validity_rate == 1.0
                and writer_result.citation_validation.evidence_trace_completeness == 1.0
                and top_hit
                and top_hit.pmid
            ),
        }
    finally:
        session.close()

    report_path = PROJECT_ROOT / "data" / "eval" / "reports" / "latest" / "retrieval_grounded_writer_validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit("Retrieval-grounded writer validation failed.")


if __name__ == "__main__":
    main()
