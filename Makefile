.PHONY: install test lint typecheck run migrate smoke verify-prototype db-up db-down

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	python -m ruff check .

typecheck:
	python -m mypy src

run:
	python -m uvicorn research_agent.api.app:app --reload

migrate:
	python -m research_agent.cli migrate

smoke:
	python scripts/smoke_test.py

verify-prototype:
	python scripts/verify_prototype.py

db-up:
	docker compose up -d postgres

db-down:
	docker compose down
