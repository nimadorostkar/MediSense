.PHONY: install dev test lint format type check seed run docker-up docker-down smoke

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --port 8787

run:
	uvicorn app.main:app --port 8787

test:
	pytest -q

lint:
	ruff check app tests

format:
	ruff format app tests

type:
	mypy app

# Full CI gate: lint + types + tests (safety golden suite included).
check: lint type test

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

smoke:
	curl -s localhost:8787/api/health; echo
	curl -s -X POST localhost:8787/api/clinical -H 'content-type: application/json' \
	  -d '{"messages":[{"role":"doctor","text":"67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60"}],"lang":"en"}'; echo
