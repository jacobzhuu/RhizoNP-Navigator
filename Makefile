PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: setup lint type test secret-scan check db-up db-down db-migrate bootstrap-db load-demo-fixtures load-literature-fixtures fetch-domain-corpus ingest-domain-corpus eval-retrieval eval-real-retrieval export-annotation-candidates import-annotation-labels run-leakage-audit eval-end-to-end demo smoke docker-test frontend-dev frontend-build frontend-typecheck app

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install pytest ruff mypy

lint:
	ruff check .

type:
	mypy src

test:
	$(PYTHON) -m pytest

secret-scan:
	$(PYTHON) -m scripts.check_no_secrets

check: secret-scan lint type test

db-up:
	$(COMPOSE) up -d postgres

db-down:
	$(COMPOSE) down

db-migrate:
	alembic upgrade head

bootstrap-db:
	$(PYTHON) -m scripts.bootstrap_db

load-demo-fixtures:
	$(PYTHON) -m scripts.load_demo_fixtures

load-literature-fixtures:
	$(PYTHON) -m scripts.load_literature_fixtures

fetch-domain-corpus:
	$(PYTHON) -m scripts.build_domain_corpus --fetch

ingest-domain-corpus:
	$(PYTHON) -m scripts.build_domain_corpus --ingest

eval-retrieval:
	$(PYTHON) -m scripts.run_retrieval_eval

eval-real-retrieval:
	$(PYTHON) -m scripts.run_retrieval_eval --real-benchmark data/eval/phase2_real_pubmed_benchmark.json

export-annotation-candidates:
	$(PYTHON) -m scripts.export_annotation_candidates

import-annotation-labels:
	@echo "Usage: make import-annotation-labels REVIEW=path/to/reviewed.csv"
	@test -n "$(REVIEW)"
	$(PYTHON) -m scripts.import_annotation_labels --review $(REVIEW)

report-qc-consistency:
	@echo "Usage: make report-qc-consistency REVIEW=path/to/reviewed.csv"
	@test -n "$(REVIEW)"
	$(PYTHON) -m scripts.report_qc_consistency --review $(REVIEW)

run-leakage-audit:
	$(PYTHON) -m scripts.run_leakage_audit

eval-end-to-end:
	$(PYTHON) -m scripts.run_end_to_end_eval

validate-real-pubmed-bridge:
	$(PYTHON) -m scripts.validate_real_pubmed_bridge

demo:
	$(PYTHON) -m scripts.run_demo

smoke:
	$(PYTHON) -m scripts.run_smoke

start:
	bash scripts/start.sh all

start-api:
	bash scripts/start.sh api

test-api:
	bash scripts/test_api_integration.sh --base-url http://127.0.0.1:8000

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-typecheck:
	cd frontend && npm run typecheck

app:
	bash scripts/start.sh app

docker-test:
	$(COMPOSE) up --build --abort-on-container-exit --exit-code-from app app
