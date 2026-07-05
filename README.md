# RhizoNP Navigator

**RhizoNP Navigator** is an evidence-grounded AI-for-Science system for connecting plant–microbe omics observations with microbial natural-product literature and candidate evidence.

It is **not** an autonomous agent, a production-scale PubMed search engine, or a claim that genus-level 16S data proves strain-level metabolite production. The MVP prioritizes traceable evidence, taxonomy-aware grading, abstention, and reproducible offline demos.

Full migration design: [`RHIZONP_NAVIGATOR_MIGRATION_PLAN.md`](RHIZONP_NAVIGATOR_MIGRATION_PLAN.md)

---

## Scientific motivation

Plant–microbe and rhizosphere studies often produce:

- 16S taxonomic signals (frequently genus-level),
- LC-MS metabolite features (often unconfirmed),
- internal association networks (correlation, not causation).

RhizoNP Navigator helps connect those **internal observations** to **external literature and structured candidate records** while enforcing:

- taxonomy distance (strain / species / genus / higher) via bounded NCBI cache or local fixture (`taxonomy_source=auto` default),
- evidence tiers (A / B / C / D),
- explicit limitations and refusal states,
- provenance from chunk → paper → source.

---

## Architecture overview

```text
Own omics CSV / demo fixtures
        │
        ▼
Literature query bridge + retrieval (Phase 5.1, optional DB-backed)
        │
        ▼
Taxonomy normalization + evidence grading (Phase 3)
        │
        ▼
Natural product candidate linking (Phase 4)
        │
        ├──────────────┐
        ▼              ▼
Literature retrieval   Structured NP fixtures
(Phase 2)              (Phase 4)
        │              │
        └──────┬───────┘
               ▼
Evidence-grounded writer (Phase 6)
               │
               ▼
Evaluation + demo package (Phase 7/8)
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

Core packages live under `src/rhizonp/` (`domain`, `literature`, `taxonomy`, `linking`, `omics`, `writer`, `evaluation`, `demo`, `api`).

---

## Phase 0–8 capability summary

| Phase | Status | MVP capability |
|---|---|---|
| 0 | Complete | CI, secret scan, cross-platform config, legacy RAGNavigator wrappers |
| 1 | Complete | SQLAlchemy schema, repositories, read-only entity API |
| 2 | **Engineering complete / empirical validation pending** | Literature chunking, BM25/dense/hybrid retrieval, provenance trace, bounded PubMed corpus workflow, annotation export |
| 3 | Complete (MVP) | Taxonomy normalization, distance, evidence tier, overclaim prevention |
| 4 | Complete (MVP) | Fixture-backed natural-product candidate linking |
| 5 | Bridge implemented / bounded PubMed validated | Own-data CSV + literature retrieval bridge + NP linking; real bounded PubMed corpus integration validated (`make validate-real-pubmed-bridge`); real applicant omics validation pending |
| 6 | Complete (MVP) | Deterministic grounded writer; optional LLM path falls back offline |
| 7 | Complete (MVP) | Offline end-to-end evaluation suite |
| 8 | Complete (MVP) | `make smoke`, `make demo`, documentation |

Phase status details: [`docs/PHASE_STATUS.md`](docs/PHASE_STATUS.md)

**Phase 2 empirical note:** real PubMed human relevance labeling (543 pooled annotation items) remains **pending**. No production retrieval quality or PubMed-wide performance claims are made without completed human labels. See [`docs/PHASE2_CLOSURE_AUDIT.md`](docs/PHASE2_CLOSURE_AUDIT.md).

---

## Three demo cases (offline)

Run locally with deterministic fixtures — no network required:

| Case | Command output | What it shows |
|---|---|---|
| **1. Literature retrieval** | `data/output/demo/case1_*` | Rhizosphere / plant–microbe query with chunk → paper provenance trace |
| **2. Taxonomy safety** | `data/output/demo/case2_*` | Genus-level 16S observation vs strain-level literature; overclaim warnings |
| **3. Own-data-to-literature** | `data/output/demo/case3_*` | Synthetic associations → literature retrieval (bounded fixture corpus when enabled) + NP candidate matrix |

```bash
make smoke    # quick 3-case validation
make demo     # full demo outputs
make validate-real-pubmed-bridge  # bounded PubMed own-data bridge validation (local corpus snapshot)
```

Runtime demo outputs are **regenerated locally** and gitignored under `data/output/`. Tracked public fixtures live under `data/fixtures/`.

---

## Quickstart

```bash
python -m pip install -r requirements.txt
python -m pip install pytest ruff mypy

make smoke
make demo
make check
```

Optional API server:

```bash
uvicorn rhizonp.api.app:app --app-dir src --reload
```

More detail: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)

### Key API endpoints

- `GET /api/v1/health`
- `GET /api/v1/taxa/{canonical_name}`
- `POST /api/v1/search`
- `POST /api/v1/taxonomy/grade`
- `POST /api/v1/natural-products/link`
- `POST /api/v1/own-data/pipeline`
- `POST /api/v1/writer/answer`

### Key CLI entrypoints

```bash
python -m scripts.grade_taxonomy_evidence "Streptomyces" "Streptomyces hygroscopicus OS-2"

Bounded NCBI taxonomy cache validation (offline):

```bash
make validate-ncbi-taxonomy-resolver
```
python -m scripts.run_own_data_pipeline
python -m scripts.run_end_to_end_eval
python -m scripts.run_demo
python -m scripts.run_smoke
```

---

## Evaluation scope

RhizoNP Navigator reports metrics **only within declared benchmark scope**:

| Benchmark | Scope | Labels | Use |
|---|---|---|---|
| `data/eval/phase2_retrieval_gold.json` | 3-query synthetic literature fixture | Explicit source-hash gold | Offline retrieval regression (`make eval-retrieval`) |
| `data/eval/end_to_end_cases.json` | Deterministic MVP replay cases | Built-in expected outcomes | End-to-end suite (`make eval-end-to-end`) |
| `data/eval/writer_safety_cases.json` | 16-case writer abstention/conflict/bounded-answer safety set | Built-in expected status + forbidden patterns | Writer safety regression (`make eval-writer-safety`) |
| `data/eval/phase2_real_pubmed_benchmark.json` | 18 real PubMed queries | **Human labels pending** | Blocked until annotation import |

**Do not interpret** perfect scores on the 3-query synthetic gold, MVP replay cases, or writer safety benchmark as PubMed-wide retrieval accuracy or human-validated scientific faithfulness. See [`docs/BENCHMARK_SCOPE.md`](docs/BENCHMARK_SCOPE.md).

Regenerated evaluation reports are written to `data/eval/reports/latest/` (gitignored).

---

## Provenance principles

- Every retrieval result traces `chunk_id → paper_id → DOI/source_url`.
- Candidate links and answers carry `provenance`, `evidence_tier`, `limitations`, and `warnings`.
- Synthetic fixtures are explicitly marked `fixture: true` and are not real experimental evidence.
- Upstream RAGNavigator lineage and migration boundaries: [`docs/PROVENANCE.md`](docs/PROVENANCE.md)

---

## Limitations (explicit)

This MVP **does not** include:

- NPAtlas, MIBiG, Crossref, or OpenAlex integrations,
- production-scale literature indexing,
- an autonomous multi-tool agent,
- completed Phase 2 human relevance evaluation,
- confirmed strain-level production claims from genus-level 16S alone,
- causal inference from correlation/co-occurrence alone.

Full list: [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)

---

## Installation and legacy Phase 0 workflow

RhizoNP Navigator preserves the original RAGNavigator chain (CSV → embedding → FAISS → reranker → PostgreSQL → LLM) for backward compatibility.

```bash
cp .env.example .env   # configure locally; never commit secrets
pip install -r requirements.txt
pip install -e ".[dev]"
make check
```

Legacy entrypoints (`src/Main.py`, etc.) remain as wrappers; prefer `python -m rhizonp.*`.

Phase 0 vector DB workflow:

```bash
cd src
python -m rhizonp.download_model
python -m rhizonp.make_vector_db
python -m rhizonp.main
```

Database and fixtures:

```bash
make db-up
alembic upgrade head
make load-demo-fixtures
make load-literature-fixtures
```

Security: [`docs/SECURITY.md`](docs/SECURITY.md) · Data model: [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)

---

## Documentation index

| Document | Purpose |
|---|---|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | Fresh-user commands |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | Scope boundaries |
| [`docs/PHASE_STATUS.md`](docs/PHASE_STATUS.md) | Phase completion table |
| [`docs/PHASE2_CLOSURE_AUDIT.md`](docs/PHASE2_CLOSURE_AUDIT.md) | Phase 2 engineering vs empirical status |
| [`docs/BENCHMARK_SCOPE.md`](docs/BENCHMARK_SCOPE.md) | What metrics may and may not claim |
| [`docs/PROVENANCE.md`](docs/PROVENANCE.md) | Upstream lineage and scientific boundaries |

---

## License and contributions

See repository history and `docs/PROVENANCE.md` for upstream baseline and migration contributions.
