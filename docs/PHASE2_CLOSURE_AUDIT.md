# Phase 2 Closure Audit

**Date:** 2026-07-05  
**Scope:** Literature provenance baseline, local retrieval, bounded PubMed corpus, offline + real benchmark workflow

> **Post-audit addendum (MVP release):** Phases 3–8 MVP engineering is complete. This document remains the authoritative Phase 2 closure record. **Phase 2 empirical human relevance evaluation is still pending** and was not reopened for this release.

---

## Engineering Definition of Done

| Requirement | Status | Evidence |
| --- | --- | --- |
| Literature adapter boundary | **Met** | `SourceAdapter`, `SyntheticLiteratureAdapter`, `PubMedEutilitiesAdapter` |
| Paper/chunk schema + Alembic | **Met** | `0002_literature_provenance`, `paper_chunks`, `retrieval_runs`, `retrieval_results` |
| Structured chunking with provenance | **Met** | `rhizonp.literature.chunking` |
| BM25 / dense / hybrid / rerank retrieval | **Met** | `search_paper_chunks`, API `retrieval_mode` |
| Metadata filters | **Met** | Column + metadata-backed filters |
| Source tracing `chunk → paper → DOI/source` | **Met** | API tests, retrieval trace |
| Embedding adapter (hash + optional HF) | **Met** | `rhizonp.literature.embeddings` |
| Optional FAISS vector index | **Met** | `FaissLiteratureVectorIndex` (skipped in CI when unavailable) |
| Reranker adapter (none / lexical / optional BGE) | **Met** | `rhizonp.literature.reranker` |
| Bounded PubMed metadata corpus workflow | **Met** | `scripts/build_domain_corpus.py`, versioned snapshots |
| Offline synthetic benchmark | **Met** | `phase2_retrieval_gold.json`, `run_retrieval_eval.py` |
| Real PubMed benchmark format (PMID, graded 0/1/2) | **Met** | `phase2_real_pubmed_benchmark.json` |
| Human annotation export/import workflow | **Met** | Pooled export, blind sheet + provenance sidecar, import validation |
| Cross-platform + offline CI | **Met** | `make check`, 82 passed / 3 skipped |
| Phase 3 not started (at audit time) | **Superseded** | Phases 3–8 MVP completed after this audit; see `docs/PHASE_STATUS.md` |

---

## Empirical Definition of Done

| Requirement | Status | Notes |
| --- | --- | --- |
| Real PubMed corpus snapshot (100–250 deduplicated records) | **Met** | 149 records in `data/snapshots/pubmed/rhizonp_domain_v1/` |
| Immutable/versioned snapshot + manifest + checksums | **Met** | `corpus.json` + `manifest.json` |
| 15–20 domain benchmark queries | **Met** | 18 queries in `phase2_real_pubmed_benchmark.json` |
| Human relevance labels (0/1/2) | **Not met** | `annotation_status: pending`; no fabricated labels |
| Offline retrieval comparison on real labels | **Blocked** | Eval runs but reports zero labeled queries until import |
| Model-backed / BGE systems on real corpus | **Optional / not empirically validated** | Supported via flags; not required for Phase 2 engineering DoD |

**Phase 2 is not fully closed on empirical DoD** because human annotation has not been completed.

---

## Real Corpus Status

| Field | Value |
| --- | --- |
| Corpus ID | `rhizonp_domain_v1` |
| Records | 149 (deduplicated by PMID) |
| Fetched at | 2026-07-05T06:10:12+00:00 |
| Metadata only | `true` |
| Full text | `false` |
| Query config | `data/eval/domain_corpus_queries.json` (17 bounded queries, max 200) |
| Snapshot path | `data/snapshots/pubmed/rhizonp_domain_v1/corpus.json` |
| Manifest checksum | `218f376184263451fb524db780bb9389a5c072cbadf02a2690f28e3c89fe95d7` |

Provenance preserved per record: PMID, DOI (when available), source URL, fetch/query provenance, adapter metadata.

---

## Real Annotation Status

| Field | Value |
| --- | --- |
| Benchmark ID | `phase2_real_pubmed_v1` |
| Queries defined | 18 |
| Queries labeled | 0 |
| Annotation status | `pending` |
| Pool export | Local `blind_reviewer_sheet.csv` + `provenance_sidecar.csv` (gitignored; regenerate) |
| Blind ordering | Deterministic within-query shuffle (seed `20260705`); no rank/score in blind sheet |
| QC duplicates | Optional via `--qc-fraction`; disabled by default |
| Public git corpus | `pmids.json` + manifest; `corpus.json` gitignored (regenerate locally) |

### Workflow

See `docs/ANNOTATION_POLICY.md` for grades, metric semantics, and unjudged-document policy.

```bash
# 1. Ingest snapshot (offline)
DATABASE_URL=sqlite+pysqlite:///./rhizonp.db make ingest-domain-corpus

# 2. Export pooled blind candidates + provenance sidecar
DATABASE_URL=sqlite+pysqlite:///./rhizonp.db make export-annotation-candidates

# 3. Run corpus/benchmark leakage audit (lexical warnings only)
make run-leakage-audit

# 4. Fill grade column (0/1/2) in blind sheet, then import
DATABASE_URL=sqlite+pysqlite:///./rhizonp.db \
  make import-annotation-labels REVIEW=data/eval/annotation/blind_reviewer_sheet.csv

# 5. Run real benchmark evaluation (offline, after labels exist)
DATABASE_URL=sqlite+pysqlite:///./rhizonp.db make eval-real-retrieval
```

---

## Evaluation Status

| Benchmark | Type | Labels | CI default |
| --- | --- | --- | --- |
| `phase2_retrieval_gold.json` | Synthetic fixture | Explicit gold (source_hash) | Yes (`make eval-retrieval`) |
| `phase2_real_pubmed_benchmark.json` | Real PubMed (PMID) | Pending human review | No (requires corpus ingest) |

Supported systems (when labels exist): BM25, dense_hash, hybrid_hash, hybrid_rerank_lexical; optional dense_model, hybrid_model, hybrid_rerank_bge.

Metrics: Recall@5, Recall@10, MRR@10, nDCG@10 (graded for real benchmark).

No production retrieval quality claims are made without completed human labels.

---

## Limitations

1. Human annotation is the remaining empirical blocker.
2. FAISS parity tests skip when `faiss-cpu` is unavailable.
3. Model-backed embedding and BGE reranker require optional heavy dependencies.
4. Live PubMed fetch requires network and NCBI policy compliance (`NCBI_EMAIL` recommended).
5. PostgreSQL container migration not re-verified in this session (Docker daemon unavailable).
6. Phase 3 taxonomy-aware evidence grading not started **at audit time** (now complete as MVP — see `docs/PHASE_STATUS.md`).

---

## Remaining Blockers (Phase 2 empirical only)

1. **Complete human relevance labeling** for `phase2_real_pubmed_benchmark.json`.
2. **Run real-corpus evaluation** after label import and record metrics.
3. Optional: FAISS environment parity verification on a machine with `faiss-cpu` installed.

---

## Post-audit scope note

At the time of this audit, Phase 3 had not started and no Crossref, OpenAlex, full-text ingestion, BGC, protein, SMILES, or agent functionality existed. Subsequent MVP work added Phases 3–8 (taxonomy grading, NP linking, own-data pipeline, grounded writer, evaluation, demo) **without** completing Phase 2 human labels or adding NPAtlas/MIBiG/agent integrations.
