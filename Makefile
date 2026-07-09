PYTHON ?= python3

.PHONY: install test lint api worker migrate compose-up compose-down inspect-sample

install:
	cd backend && $(PYTHON) -m pip install -e ".[dev]"

test:
	cd backend && $(PYTHON) -m pytest -q

lint:
	cd backend && $(PYTHON) -m ruff check app tests

api:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && $(PYTHON) -m celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO

migrate:
	cd backend && $(PYTHON) -m alembic upgrade head

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

inspect-sample:
	cd backend && python -m app.cli.main inspect-pdf "../zzsj619/中兴豫建设管理有限公司(1).pdf"
