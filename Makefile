PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: setup lint type test secret-scan check db-up db-down db-migrate bootstrap-db load-demo-fixtures load-literature-fixtures fetch-domain-corpus ingest-domain-corpus eval-retrieval eval-real-retrieval export-annotation-candidates import-annotation-labels run-leakage-audit docker-test

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

run-leakage-audit:
	$(PYTHON) -m scripts.run_leakage_audit

docker-test:
	$(COMPOSE) up --build --abort-on-container-exit --exit-code-from app app
