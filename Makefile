.PHONY: up down test run init-db install generate-data ingest

up:
	docker compose up -d
	@echo "Waiting for Postgres..."
	@sleep 3
	@$(MAKE) init-db

down:
	docker compose down

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

init-db:
	.venv/bin/python scripts/init_db.py

generate-data:
	.venv/bin/python scripts/generate_synthetic_data.py

ingest:
	.venv/bin/python scripts/run_ingestion.py

test:
	.venv/bin/pytest tests/ -v

run:
	.venv/bin/uvicorn app.main:app --host $$(grep API_HOST .env 2>/dev/null | cut -d= -f2 || echo 0.0.0.0) --port $$(grep API_PORT .env 2>/dev/null | cut -d= -f2 || echo 8000) --reload
