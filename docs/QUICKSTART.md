# Quickstart

This quickstart runs the RhizoNP Navigator MVP **offline** with deterministic fixtures. No external network access is required.

## Prerequisites

```bash
python -m pip install -r requirements.txt
python -m pip install pytest ruff mypy
```

Copy local configuration (no secrets in git):

```bash
cp .env.example .env
```

## One-command smoke test

```bash
make smoke
```

Expected result: three demo cases complete with JSON/CSV/Markdown outputs under `data/output/smoke/`.

These paths are **gitignored runtime artifacts** — regenerate them on any fresh clone.

## Full demo workflow

```bash
make demo
```

Outputs are written to `data/output/demo/`:

| Case | Output prefix | Description |
|---|---|---|
| 1 | `case1_literature_retrieval` | Literature retrieval with provenance trace |
| 2 | `case2_taxonomy_grading` | Taxonomy-aware evidence grading |
| 3 | `case3_*` | Own-data-to-literature candidate matrix |

Public-safe **input fixtures** (tracked in git): `data/fixtures/`

## Evaluation suite

```bash
make eval-end-to-end
```

Reports are written to `data/eval/reports/latest/` (gitignored). Metrics apply only to the declared synthetic/MVP replay scope — not PubMed-wide retrieval quality.

## Optional API server

```bash
uvicorn rhizonp.api.app:app --app-dir src --reload
```

Key endpoints:

- `POST /api/v1/search`
- `POST /api/v1/taxonomy/grade`
- `POST /api/v1/natural-products/link`
- `POST /api/v1/own-data/pipeline`
- `POST /api/v1/writer/answer`

## Full project checks

```bash
make check
```
