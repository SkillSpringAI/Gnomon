.PHONY: install test lint typecheck run db-up db-down

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

db-up:
	docker compose up -d postgres

db-down:
	docker compose down
