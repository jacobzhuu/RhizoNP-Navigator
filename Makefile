PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: setup lint type test secret-scan check db-up db-down db-migrate bootstrap-db load-demo-fixtures load-literature-fixtures docker-test

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

docker-test:
	$(COMPOSE) up --build --abort-on-container-exit --exit-code-from app app
