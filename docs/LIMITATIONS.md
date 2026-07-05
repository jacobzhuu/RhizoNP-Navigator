# Limitations

## Current MVP scope

- Natural product records prefer a **bounded NPAtlas snapshot** (`auto`) when present, with synthetic fixture fallback; full NPAtlas/MIBiG/Crossref/OpenAlex coverage is not implemented.
- Taxonomy normalization prefers a **bounded NCBI cache** (`auto`, 6 taxa) with local alias fixture fallback; this is not a complete NCBI Taxonomy mirror or universal strain resolver.
- Literature retrieval uses synthetic fixtures for offline demos and a **bounded real PubMed corpus** (`rhizonp_domain_v1`, ~149 records) for DB-backed integration validation; this is not production-scale or PubMed-wide indexing.
- Dense retrieval defaults to deterministic hashing embeddings unless optional model-backed providers are configured.
- LLM writer mode is optional and falls back to deterministic synthesis in offline/demo paths.
- **Phase 2 empirical human labeling** for the 543-item pooled annotation task remains **pending**. No real-benchmark retrieval quality claims are made until labels are imported.
- Own-data pipeline literature retrieval requires an enabled flag and DB-backed corpus session; default offline runs report `DISABLED`/`RETRIEVAL_UNAVAILABLE` rather than fabricating papers. Phase 5.2 validates the bridge against the real bounded PubMed snapshot when ingested; this does not validate retrieval relevance or real applicant omics.
- Real applicant 16S/LC-MS validation and PostgreSQL persistence of imported associations remain **pending**.

## What this system is not

- Not an autonomous agent or multi-tool loop.
- Not a PubMed-wide search engine with validated production metrics.
- Not a claim that internal 16S genus presence proves strain-level natural-product production.
- Not a causal inference engine for omics associations.

## Scientific boundaries

- Correlation or co-occurrence does not imply biochemical production or causation.
- Genus-level evidence is candidate-level only.
- Unknown LC-MS features must not be promoted to confirmed compound identities.
- Conflicting evidence returns `CONFLICTING_EVIDENCE` rather than a forced single answer.

## Evaluation boundaries

- `make eval-end-to-end` scores a small deterministic MVP replay suite (including a 3-query synthetic retrieval gold set).
- Perfect scores on that suite do **not** imply 100% retrieval accuracy on real PubMed or production corpora.
- Real PubMed benchmark evaluation (`phase2_real_pubmed_benchmark.json`) is blocked until human labels exist.

## Operational boundaries

- Tests and demos are offline by default.
- Demo and eval report outputs under `data/output/` and `data/eval/reports/latest/` are regenerated locally and gitignored.
- Docker/PostgreSQL validation may require a running Docker daemon locally.
