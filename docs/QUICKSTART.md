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
# or full bootstrap + API + integration checks:
./scripts/start.sh
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
./scripts/start.sh api          # foreground
./scripts/start.sh              # setup + DB (if Docker) + API background + test-api
./scripts/start.sh test-api     # integration checks against running API
make start-api
```

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

## Research workspace frontend

The user-facing research demo runs separately from the FastAPI backend during development.

**Terminal 1 — backend (port 8000):**

```bash
make start-api
# or: ./scripts/start.sh api
```

For literature search, load the database first:

```bash
./scripts/start.sh db
```

**Terminal 2 — frontend (port 5173):**

```bash
make frontend-dev
# or: cd frontend && npm install && npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`. Swagger remains at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for developers.

Production builds can set `VITE_API_BASE_URL` in `frontend/.env` (see `frontend/.env.example`).

```bash
make frontend-build   # compile to frontend/dist/
make frontend-typecheck
```
