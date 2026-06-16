# MediGovern RAG

Healthcare prior-authorization data-governance RAG pipeline — FHIR-aware ingestion, metadata-driven retrieval, data-quality gating, and auditable policy citations.

Companion spec: [`MediGovern_RAG_Implementation_Plan.md`](MediGovern_RAG_Implementation_Plan.md)

## Getting started

### Prerequisites

- Python 3.11+
- Docker (for local Postgres + pgvector)
- Make (optional, for convenience targets)

### 1. Clone and configure

```bash
cd medigovern-rag
cp .env.example .env
# Edit .env — set OPENAI_API_KEY or ANTHROPIC_API_KEY when ready
```

For local development without API keys, set:

```env
LLM_PROVIDER=local
EMBEDDINGS_PROVIDER=local
```

### 2. Install dependencies

```bash
make install
# or: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

### 3. Start the database

```bash
make up
```

This runs `docker compose up -d` and initializes the schema (pgvector extension + `document_metadata` table).

### 4. Confirm schema was created

```bash
docker compose exec db psql -U medigovern -d medigovern -c "\dt"
docker compose exec db psql -U medigovern -d medigovern -c "\d document_metadata"
```

You should see the `document_metadata` table with columns matching the canonical metadata model (section 5.2 of the implementation plan).

### 5. Run tests

```bash
make test
```

### 6. Start the API

```bash
make run
```

Open http://localhost:8000/health — expect `{"status":"ok","service":"medigovern-rag"}`.

## Project structure

```
app/           FastAPI service, config, pydantic models, SQLAlchemy tables
pipeline/      Ingestion, DQ, embeddings, retrieval, audit (later phases)
data/          Raw synthetic sources and generated outputs
tests/         Unit tests
scripts/       Database initialization helpers
```

## Phase 1 scope (current)

- Python 3.11 project scaffolding
- Postgres + pgvector via Docker Compose
- Canonical metadata model (pydantic + SQLAlchemy)
- Swappable LLM/embeddings provider interface (OpenAI, Anthropic, local stub)
- FastAPI skeleton with health check
- Makefile: `make up`, `make test`, `make run`

Later phases (ingestion, DQ, retrieval, audit) are stubbed under `pipeline/` and built in subsequent prompts.

## Makefile targets

| Target    | Description                          |
|-----------|--------------------------------------|
| `make up` | Start Postgres+pgvector, init schema |
| `make down` | Stop database containers           |
| `make test` | Run pytest                         |
| `make run`  | Start FastAPI dev server           |
| `make init-db` | Create pgvector + tables only   |
