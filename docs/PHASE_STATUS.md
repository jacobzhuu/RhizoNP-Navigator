# Phase Completion Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 | COMPLETE | Baseline engineering, CI, secret scan, legacy wrappers |
| Phase 1 | COMPLETE | Domain schema, repositories, read-only API |
| Phase 2 | **ENGINEERING_COMPLETE / EMPIRICAL_VALIDATION_PENDING** | Retrieval stack implemented; 543-item human labeling pending |
| Phase 3 | **TAXONOMY-AWARE GRADING IMPLEMENTED / NCBI BOUNDED AUTHORITY RESOLUTION INTEGRATED** | AUTO resolver prefers bounded NCBI cache (6 taxa) with explicit fixture fallback; full taxonomy coverage not claimed |
| Phase 4 | COMPLETE (MVP) | NPAtlas bounded AUTO on main path + fixture fallback for offline demos |
| Phase 5 | **OWN-DATA-TO-LITERATURE BRIDGE IMPLEMENTED / REAL BOUNDED PUBMED CORPUS VALIDATED** | CSV ingest + literature retrieval bridge + NP linking; bounded `rhizonp_domain_v1` PubMed integration validated (SQLite/PostgreSQL); real applicant omics validation pending |
| Phase 6 | COMPLETE (MVP) | Deterministic grounded writer with abstention/conflict states |
| Phase 7 | COMPLETE (MVP) | Offline end-to-end evaluation with JSON/Markdown reports |
| Phase 8 | COMPLETE (MVP) | `make smoke`, `make demo`, docs, offline demo cases |

## Phase 2 empirical status (unchanged)

Human relevance labeling for the real PubMed benchmark remains **pending**. Engineering artifacts (corpus snapshot, annotation export/import, leakage audit) are in place, but graded real-benchmark metrics must not be reported until labels are imported.

See [`PHASE2_CLOSURE_AUDIT.md`](PHASE2_CLOSURE_AUDIT.md) for the original Phase 2 closure record and post-audit addendum.

## Phase 5 bounded PubMed integration (Phase 5.2)

The own-data→literature bridge is validated against the **real bounded PubMed corpus** (`corpus_id=rhizonp_domain_v1`, ~149 deduplicated records from NCBI E-utilities). This is **integration validation only** — it confirms traceable PMID/DOI/source-url retrieval through `search_paper_chunks()`, not retrieval quality or PubMed-wide performance.

Run locally (requires local `data/snapshots/pubmed/rhizonp_domain_v1/corpus.json`):

```bash
make validate-real-pubmed-bridge
```

Reports are written to `data/eval/reports/latest/real_pubmed_corpus_validation.{json,md}` (gitignored). Fixture literature remains `FIXTURE_TEST_ONLY`; real corpus hits use `corpus_type=REAL_BOUNDED_PUBMED`.

## Phase 3 bounded NCBI taxonomy authority

Taxonomy grading uses **`taxonomy_source=auto` by default**: prefer the offline bounded NCBI cache (`ncbi_bounded_v1`, 6 query labels) when a match exists, otherwise fall back to the local alias fixture with explicit `requested_source` / `resolved_source` / `fallback_reason` metadata. This is **not** full NCBI Taxonomy coverage or production-scale normalization.

```bash
make validate-ncbi-taxonomy-resolver
make fetch-ncbi-taxonomy-cache   # optional network rebuild
```

## Deferred work

- Complete Phase 2 human annotation and graded real-benchmark reporting
- Optional production integrations: NPAtlas, MIBiG, model-backed embeddings, remote LLM synthesis
- Large frontend or autonomous agent workflow
