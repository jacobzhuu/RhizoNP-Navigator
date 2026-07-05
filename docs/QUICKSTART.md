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

## One-command web app

```bash
make start
# or:
./scripts/start.sh
```

This bootstraps the Python environment, starts PostgreSQL with Docker, runs migrations and
fixtures, starts FastAPI and the Vite research workspace, runs API checks, and opens:

```text
http://127.0.0.1:5173/
```

The default page is **科研问答**: enter one scientific question and the app will show the
question plan, synonym/query expansion, retrieved evidence snippets, and final grounded
answer. The remaining navigation items expose the underlying modules for inspection.

Use `RHIZONP_OPEN_BROWSER=0 make start` if you only want the URL printed.

Stop background services with:

```bash
make stop
```

## Smoke test

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

## Optional API server only

```bash
./scripts/start.sh api          # foreground
./scripts/start.sh test-api     # integration checks against running API
make start-api
```

```bash
uvicorn rhizonp.api.app:app --app-dir src --reload
```

Key endpoints:

- `GET /api/v1/health`
- `GET /api/v1/readiness`
- `POST /api/v1/ask`
- `GET /api/v1/corpus/summary`
- `POST /api/v1/search`
- `POST /api/v1/taxonomy/grade`
- `POST /api/v1/natural-products/link`
- `POST /api/v1/own-data/pipeline`
- `POST /api/v1/writer/answer`

## Production runtime mode

Use production mode when presenting or deploying the stack without implicit SQLite/fixture fallbacks:

```bash
./scripts/start.sh prod
# or:
make prod
```

Set `RHIZONP_RUNTIME_MODE=prod` in `.env` for long-running API processes. In this mode:

- PostgreSQL `DATABASE_URL` is required for DB-backed endpoints.
- Own-data pipeline requires an explicit `data_dir`.
- `/api/v1/readiness` reports `ready`, `degraded`, or `unavailable` with corpus warnings.

## Docker Compose stack

Launch PostgreSQL, migrations, API, and static frontend in one command:

```bash
docker compose up --build postgres migrate api frontend
# or:
make docker-app
```

Open the workspace at [http://127.0.0.1:8080/](http://127.0.0.1:8080/) (API proxied at `/api`).

Run containerized pytest separately:

```bash
make docker-test
```

## External presentation checklist

Before a live walkthrough:

1. Confirm header status pill is green or yellow with an understood warning.
2. Verify `GET /api/v1/readiness` returns `database.connected=true` and corpus counts > 0.
3. Run `./scripts/start.sh db` (or `docker compose up migrate`) if literature search is required.
4. Use example question chips on the Ask page instead of pre-filled demo text.
5. Review `/about/limitations` once if audience asks about data scope.

## Full project checks

```bash
make check
```

Local `.env` credentials are ignored by the test suite so private API keys do not change
deterministic test behavior. Skip counts depend on optional runtime services and packages:

- FAISS-specific tests skip when `faiss-cpu` is unavailable.
- PostgreSQL full-stack integration skips when Docker/PostgreSQL is unavailable.
- DeepSeek live evaluation is opt-in and is not part of `make check`.

## Research workspace frontend

The default `make start` command runs the backend and frontend together. Use the split
commands below only when debugging one side of the stack.

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

**One command — API + frontend (background):**

```bash
make start
# or: make app
# or: ./scripts/start.sh app
# stop: make stop
```

Prints workspace URL (`http://127.0.0.1:5173/`) and API docs (`http://127.0.0.1:8000/docs`).
