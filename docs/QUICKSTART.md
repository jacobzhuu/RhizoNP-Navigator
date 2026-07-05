# Quickstart

This quickstart runs the RhizoNP Navigator MVP offline with deterministic fixtures. No external network access is required.

## Prerequisites

```bash
python -m pip install -r requirements.txt
python -m pip install pytest ruff mypy
```

## One-command smoke test

```bash
make smoke
```

Expected result: three demo cases complete with JSON/CSV/Markdown outputs under `data/output/smoke/`.

## Full demo workflow

```bash
make demo
```

Outputs are written to `data/output/demo/`:

- Case 1: literature retrieval with provenance trace
- Case 2: taxonomy-aware evidence grading
- Case 3: own-data-to-literature candidate matrix

## Evaluation suite

```bash
make eval-end-to-end
```

Reports are written to `data/eval/reports/latest/`.

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
