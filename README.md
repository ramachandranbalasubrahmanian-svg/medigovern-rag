# MediGovern RAG

> **Healthcare prior-authorization data-governance RAG pipeline.**
> FHIR-aware ingestion · metadata-driven retrieval · data-quality gating · auditable policy citations.

**All data is 100% synthetic. No real PHI. Freely publishable.**

🔗 **Live dashboard:** [medigovern-insight.lovable.app](https://medigovern-insight.lovable.app) &nbsp;|&nbsp; **API:** [medigovern-rag-production.up.railway.app](https://medigovern-rag-production.up.railway.app)

---

## What It Is

**MediGovern RAG** is a production-grade, data-governed retrieval-augmented generation pipeline built for healthcare prior authorization. It ingests heterogeneous source data — policy PDFs, CSV benefit tables, and FHIR patient records — runs every document through a six-rule data quality gate before any embedding is stored, and answers clinical coverage questions with grounded citations, confidence scoring, and a deliberate ABSTAIN path when evidence is ambiguous or policies conflict. The result is not a chatbot layered over documents; it is an auditable decision-support system that can demonstrate, record by record, why a recommendation was made and on which policy clause it rests.

## Why It Matters: CMS-0057-F

The system is built around a real compliance deadline. [CMS-0057-F](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/policies-regulations/cms-interoperability-prior-authorization-final-rule-cms-0057-f) — the Centers for Medicare & Medicaid Services' Interoperability and Prior Authorization rule — requires health plans to respond to standard PA requests within seven business days by 2026 and urgent requests within **72 hours by 2027**, and to expose prior authorization data via standardized FHIR APIs. MediGovern RAG operationalizes those obligations: the six-rule DQ gate quarantines expired, incomplete, or conflicting policies before they corrupt a retrieval result; an immutable audit packet captures every retrieval decision; and the governance dashboard gives compliance teams real-time visibility into what the system knows, what it has rejected, and why. When a regulator asks "how did you reach that determination?", the answer is already logged.

## What Makes It Different from "Chat with PDF"

What separates MediGovern RAG from generic document Q&A is the governance layer *underneath* the generation step. Semantic search using BAAI/bge-small-en-v1.5 embeddings in pgvector grounds retrieval in actual policy text. The confidence classifier — High, Medium, or Low — is computed from retrieval scores and evidence coverage, not asserted by the model. When two retrieved clauses contradict each other, the system does not pick a side: it issues an explicit **ABSTAIN** with the conflicting sources named, giving human reviewers exactly the information they need without fabricating a resolution. Missing patient context required for a PA determination surfaces as a structured gap, not a hallucination. Every query, every retrieved chunk, and every generated answer is stored as a full lineage record. That audit trail is the product — the answers are a byproduct of it.

---

## Architecture

```
SOURCES                INGESTION              GOVERNANCE GATE         KNOWLEDGE LAYER      SERVING
──────                 ─────────              ───────────────         ───────────────      ───────
Policy PDFs       ┐                      ┌─ Metadata extraction   ┌─ Chunking             ┌─ Metadata pre-filter
Clinical guides   │                      │  (type, IDs, dates,    │  + embeddings         │  (plan/payer/CPT/date)
Plan benefits     ├─► pipeline/         ─┤  CPT/ICD, payer, plan) ├─► pgvector +       ──►├─ Semantic search
FHIR bundles      │   ingestion/         │                         │  metadata index       │
Provider dir      │   (typed loaders)    └─ DQ rule engine         └─ Lineage pointers     ├─ Cited answer
Claims CSV        ┘                         (6 rule families)                              │  + confidence band
                                            pass / warn / quarantine                       ├─ Audit packet
                                                    │                                      │  (JSON + HTML)
                                                    ▼                                      └─ Immutable audit log
                                          Quarantine queue
                                          DQ report (JSON)
```

**Stack:** Python 3.11 · FastAPI · SQLAlchemy · Postgres + pgvector · pydantic · reportlab · pypdf · Anthropic Claude (LLM) · fastembed/ONNX (embeddings, no API key) · Docker Compose

---

## Getting started locally

### Prerequisites
- Python 3.11+
- Docker (for Postgres + pgvector)

### 1. Clone and configure

```bash
git clone https://github.com/ramachandranbalasubrahmanian-svg/medigovern-rag.git
cd medigovern-rag
cp .env.example .env
# Add your Anthropic key (only API key required — embeddings are free/local):
#   ANTHROPIC_API_KEY=sk-ant-...
# To run fully offline without any API key (stub mode):
#   LLM_PROVIDER=local
#   EMBEDDINGS_PROVIDER=local
#   EMBEDDING_DIMENSION=8
```

### 2. Install dependencies

```bash
make install
# or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

### 3. Start the database and seed the knowledge base

```bash
make up                  # starts Postgres+pgvector, runs init_db
make generate-data       # generates 12 synthetic policy PDFs + CSV + FHIR bundles
make ingest-and-index    # load → DQ gate → chunk → embed → pgvector
```

Or — if `SEED_ON_STARTUP=true` (the default), the first `make run` will auto-seed on startup.

### 4. Confirm the schema

```bash
docker compose exec db psql -U medigovern -d medigovern -c "\dt"
# Tables: document_metadata, document_chunks, audit_log
```

### 5. Run tests

```bash
make test
# 51 passed, 1 skipped (DB integration — needs Postgres)
```

### 6. Start the API

```bash
make run
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger)
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check (DB ping) |
| `POST` | `/ask` | Ask a prior-auth question |
| `GET` | `/audit/{id}` | Full audit packet (JSON) |
| `GET` | `/audit/{id}/html` | Rendered HTML audit report |
| `GET` | `/audit` | Recent query history |
| `GET` | `/policies` | Policy catalog (filterable) |
| `GET` | `/policies/{id}` | Single policy detail |
| `GET` | `/quarantine` | Quarantined records + DQ reasons |
| `GET` | `/providers/status` | LLM/embeddings config status |
| `GET` | `/docs` | Swagger UI |

### Example: POST /ask

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Does CPT 70553 require prior authorization for this plan?",
    "plan_id": "GOLD-PPO",
    "payer": "AcmeHealth",
    "cpt": "70553"
  }'
```

Response:
```json
{
  "audit_packet_id": "...",
  "answer": "⛔ NEEDS HUMAN REVIEW — Conflicting policies detected...",
  "confidence": "ABSTAIN",
  "confidence_rationale": "Active policies with conflicting PA requirements...",
  "citations": [...],
  "missing_data": [],
  "abstained": true,
  "abstain_reason": "Conflict: POL-70553-A (PA=YES) vs POL-70553-B (PA=NO)"
}
```

### Example: GET /policies

```bash
curl "http://localhost:8000/policies?payer=AcmeHealth&cpt=70553"
```

### Example: GET /quarantine

```bash
curl http://localhost:8000/quarantine
# Returns the 4 seeded governance defects:
# POL-70553-EXP (expired), POL-70553-A + POL-70553-B (conflict), POL-NODATE (missing date)
```

---

## The 5 demo questions

These anchor the build and the demo video. Run them with:

```bash
make eval          # requires running Postgres + seeded index
make eval-offline  # logic-only (no DB needed) ✓
```

| # | Question | Expected behaviour |
|---|----------|--------------------|
| Q1 | Does CPT 70553 require prior authorization for GOLD-PPO? | **ABSTAIN** — conflicting policies |
| Q2 | Which policy supports the denial reason for a knee replacement? | Answer citing POL-27447 |
| Q3 | What patient data is missing before submitting auth for CPT 70553? | Lists missing data; expired policy excluded |
| Q4 | Are there conflicting coverage rules for CPT 70553 on GOLD-PPO? | **ABSTAIN** — surfaces conflict detail |
| Q5 | Show the lineage for the prior auth recommendation for CPT 93306. | Cited answer with lineage from POL-93306 |

---

## Deploying to Railway (free tier)

Railway auto-detects the `Dockerfile` and provisions a Postgres add-on.

### Steps

1. Push this repo to GitHub (already done).
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**.
3. Select `medigovern-rag`. Railway builds the image from `Dockerfile`.
4. In the **Variables** tab, add:

```
DATABASE_URL          ${{Postgres.DATABASE_URL}}   # auto-injected from Postgres addon
LLM_PROVIDER          anthropic
ANTHROPIC_API_KEY     sk-ant-...
ANTHROPIC_MODEL       claude-haiku-4-5
EMBEDDINGS_PROVIDER   sentence-transformers
SEED_ON_STARTUP       true
CORS_ORIGINS          https://your-lovable-app.lovable.app,http://localhost:3000
```

> **No OpenAI key needed.** Embeddings run locally via `fastembed` (ONNX, baked into the image).

5. Add a **Postgres** plugin from the Railway dashboard. Railway injects `DATABASE_URL` automatically.
6. **Deploy** — Railway builds the image (pre-downloads the embedding model), runs `generate_synthetic_data.py`, then on first boot seeds the knowledge base automatically.
7. Your base URL: `https://<project>.up.railway.app`

### Deploying to Render (free tier)

1. Go to [render.com](https://render.com) → **New Web Service → Connect GitHub**.
2. Runtime: **Docker**. Build command: *(auto from Dockerfile)*.
3. Add a **PostgreSQL** database from the Render dashboard; copy the **Internal Database URL**.
4. Set the same env vars as above, with `DATABASE_URL` pointing to Render's internal URL.
5. Deploy. On first start the API seeds itself.

### Required environment variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | Postgres connection string with pgvector | Yes |
| `LLM_PROVIDER` | `anthropic` / `openai` / `local` | Yes (default `anthropic`) |
| `ANTHROPIC_API_KEY` | Anthropic API key | Yes (when `LLM_PROVIDER=anthropic`) |
| `ANTHROPIC_MODEL` | Model name | Optional (default `claude-haiku-4-5`) |
| `EMBEDDINGS_PROVIDER` | `sentence-transformers` / `openai` / `local` | Yes (default `sentence-transformers`) |
| `SEED_ON_STARTUP` | Auto-seed on empty DB (`true`/`false`) | Optional (default `true`) |
| `CORS_ORIGINS` | Comma-separated allowed origins | Optional |

---

## Seeded governance defects

The synthetic data deliberately seeds defects for the DQ layer to catch on camera:

| Defect | Document | Rule | Status |
|--------|----------|------|--------|
| **Expired policy** | `POL-70553-EXP` (expiry 2024-01-01) | `timeliness.expired` | QUARANTINED |
| **Conflicting PA rules** | `POL-70553-A` (PA=YES) + `POL-70553-B` (PA=NO) same CPT/plan | `consistency.conflict` | QUARANTINED |
| **Missing effective date** | `POL-NODATE` | `completeness.missing_effective_date` | QUARANTINED |
| **Duplicate NPI** | Dr. Alice Chen × 2 | `uniqueness.duplicate_npi` | WARNING |
| **Invalid NPI checksum** | Dr. Invalid One/Two | `validity.invalid_npi` | WARNING |
| **Missing patient diagnosis** | `patient_bundle_003.json` | `patient_context.missing_diagnosis` | WARNING |

---

## Built with AI

Architecture, governance design, and all key decisions were made by me: the six-rule data quality framework, the ABSTAIN logic and when it fires, confidence scoring thresholds, audit schema design, and the CMS-0057-F compliance mapping. **Cursor** (AI coding agent) implemented the entire Python backend — ingestion pipeline, DQ gate, chunking and embedding, RAG retrieval loop, FastAPI endpoints, and SQLAlchemy models. **Lovable** (AI UI agent) built the React governance dashboard — Overview, Policy Catalog with filters, Quarantine Queue, Ask/Q&A, and Audit Viewer — from my design specifications. The AI agents wrote the code. I specified what the code needed to do, why it needed to do it, and what "correct" looks like in a healthcare compliance context.

### Human decisions (the things that make it senior, not a student project)

- **Metadata model as governance backbone** — choosing to make the canonical metadata record (section 5.2: `policy_id`, `payer`, `plan_id`, `effective_date`, `expiry_date`, `procedure_codes`, `dq_status`, `dq_findings`) the governance spine that flows through ingestion, chunking, retrieval, and audit. This is a DAMA-DMBOK design choice, not a technical default.

- **DQ gate before embedding, not after** — deliberately quarantining records *before* they reach the vector store so expired/conflicting/incomplete policies can never be retrieved, even accidentally. Most RAG demos skip this entirely.

- **Abstain-on-conflict, not best-guess** — choosing to return "NEEDS HUMAN REVIEW" when active policies conflict, rather than picking the more recent one. This is the correct clinical-governance stance and the key differentiator vs "chat with PDF."

- **Audit packet as a first-class artifact** — making every answered question produce an immutable, downloadable audit packet (question → filters → retrieved chunks with lineage → answer → confidence) before writing a single line of retrieval code. This is what lets you say "auditable" with a straight face in a CMS-0057-F context.

- **Synthetic data seeded with deliberate defects** — designing the test data to *fail* specific DQ rules (expired policy, two conflicting policies for the same CPT, missing effective date) so the governance layer has something to catch on camera. A governance demo without failing cases is just a CRUD app.

- **Confidence in 3 bands, not a raw score** — choosing High/Medium/Low/ABSTAIN rather than a 0–1 float because clinical decision-support requires human-interpretable signals, not calibrated probabilities.

### What AI agents implemented

**Cursor (backend):**
- All Python code (ingestion loaders, DQ rule engine, chunker, pgvector indexer, retriever, generator, audit HTML renderer, FastAPI routes)
- SQLAlchemy table definitions, Dockerfile, Railway deploy config
- Test suite (51 tests)
- Synthetic data generation script (12 PDFs with embedded metadata, FHIR bundles, CSVs)

**Lovable (frontend):**
- React governance dashboard — Overview, Policy Catalog with live filters, Quarantine Queue, Ask/Q&A with confidence badges, Audit Viewer with download
- Server-side API proxy (solved CORS across all environments)
- Supabase auth integration

---

## Project structure

```
app/
  api/          FastAPI routers (ask, audit, catalog)
  db/           SQLAlchemy ORM models
  models/       Pydantic models (metadata, chunk, audit)
  providers/    LLM + embeddings interfaces (OpenAI, Anthropic, local stub)
  config.py     Settings from .env
  database.py   Engine, sessions, init_db
  main.py       FastAPI app + CORS + startup seeding

pipeline/
  ingestion/    Typed loaders (PDF, CSV, FHIR) + DQ pipeline
  dq/           Rule engine (6 rule families) + report
  embeddings/   Chunker + pgvector indexer + ingest-and-index orchestrator
  retrieval/    Metadata pre-filter + semantic search + conflict detector
  audit/        Audit packet model + append-only log + HTML renderer

data/
  raw/          Synthetic source files (generated, not committed)
  generated/    DQ reports, index reports

scripts/
  generate_synthetic_data.py
  run_ingestion.py
  ingest_and_index.py
  eval_demo_questions.py
  init_db.py

tests/          51 unit + integration tests

lovable/        GA4 + Clarity integration files for medigovern-insight.lovable.app dashboard
```

---

## Dashboard analytics (GA4 + Clarity)

Visitor analytics for the **Lovable dashboard** (`medigovern-insight.lovable.app`) — country, traffic source, session recordings, and RAG-specific events (queries, audit downloads).

**Setup:** See [`lovable/LOVABLE_ANALYTICS_PROMPT.md`](lovable/LOVABLE_ANALYTICS_PROMPT.md) — paste the prompt into Lovable, add your GA4/Clarity IDs, and publish.

---

## Sources

- [CMS-0057-F — Interoperability and Prior Authorization Final Rule](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/policies-regulations/cms-interoperability-prior-authorization-final-rule-cms-0057-f)
- [DAMA-DMBOK — Data Management Body of Knowledge](https://dama.org/learning-resources/dama-data-management-body-of-knowledge-dmbok/)
- [HL7 FHIR R4 Overview](https://hl7.org/fhir/overview.html)
- [Synthea Synthetic Patient Generator](https://synthetichealth.github.io/synthea/)
- [pgvector](https://github.com/pgvector/pgvector)
