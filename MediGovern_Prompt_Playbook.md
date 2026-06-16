# MediGovern RAG — Prompt Playbook
### Copy-paste prompts for Cursor (primary) + Lovable + Claude Cowork

**For:** Ramachandran Balasubrahmanian · **Deadline:** Friday
**How to use:** Run the prompts **in order**. Each one is a self-contained instruction. Wait for one to finish, review/commit, then run the next. Don't paste them all at once.

> Companion to `MediGovern_RAG_Implementation_Plan.md`. Keep that plan file in your repo root so the agent can reference it.

---

## Setup before you start (5 minutes, do once)

1. Create an empty folder, e.g. `medigovern-rag`, and open it in **Cursor**.
2. Drop `MediGovern_RAG_Implementation_Plan.md` into the folder root.
3. Initialize git: in Cursor's terminal run `git init`.
4. Open Cursor **Agent mode** (the chat panel, Agent tab). Set model to **Claude Sonnet** for the hard phases (2, 4); use **Auto** for routine work to conserve premium requests.
5. Get an LLM API key ready (OpenAI or Anthropic) for embeddings + generation — you'll paste it into a `.env` when prompted.

**Model strategy to protect your credits:** Sonnet for Prompts 2, 4, 5 (logic-heavy). Auto for Prompts 1, 3, 6, 7 (scaffolding/glue/fixes).

---

# PART A — CURSOR (backend, the whole pipeline)

### ▶ PROMPT 1 — Project scaffolding & foundations *(model: Auto)*

```
You are building "MediGovern RAG", a healthcare prior-authorization data-governance RAG pipeline. Read MediGovern_RAG_Implementation_Plan.md in the repo root and follow it as the source of truth.

Implement PHASE 1 (Foundations) only. Do NOT build later phases yet.

Tasks:
1. Create a Python 3.11 project with this structure:
   - app/  (FastAPI service)
   - pipeline/ (ingestion, dq, embeddings, retrieval, audit)
   - data/ (raw synthetic sources + generated outputs)
   - tests/
   - requirements.txt, .env.example, README.md, .gitignore
2. Use these defaults: FastAPI, SQLAlchemy + Postgres with pgvector, pydantic for models. Provide a docker-compose.yml that runs Postgres+pgvector locally so I can develop without installing Postgres.
3. Implement the canonical metadata model from section 5.2 of the plan as a pydantic model AND a SQLAlchemy table.
4. Create a config module that reads an LLM/embeddings API key from .env. Keep the model provider behind a swappable interface (so I can switch OpenAI/Anthropic/local).
5. Add a Makefile or simple scripts: `make up` (start db), `make test`, `make run` (start API).
6. Write a clear README "Getting started" section.

Constraints: keep it minimal and runnable. After you finish, tell me the exact commands to start the database and confirm the schema was created. Then stop.
```

---

### ▶ PROMPT 2 — Synthetic data + ingestion + data-quality gate *(model: Sonnet)*

```
Continue MediGovern RAG. Implement PHASE 2 (Synthetic data + Ingestion + Governance/DQ gate) from the plan (sections 5.3, 5.4, 5.2). Do not build embeddings/retrieval yet.

A. SYNTHETIC DATA (section 5.3) — generate into data/raw/:
   - 12 short synthetic "payer medical policy" PDFs covering a few procedures, centered on CPT 70553 (MRI brain) plus 2-3 others. Use reportlab or similar to generate the PDFs.
   - DELIBERATELY seed governance defects: exactly one EXPIRED policy (expiry_date in the past), TWO policies with CONFLICTING prior-auth rules for the SAME CPT+plan, and ONE policy MISSING an effective_date.
   - A provider directory CSV with deliberate DUPLICATE NPIs and 2 invalid NPIs.
   - A claims-like CSV linking member, CPT, plan, outcome.
   - A few synthetic FHIR R4 patient bundles as JSON (hand-craft minimal valid bundles; note in README that Synthea can replace these later). Make at least one bundle MISSING the diagnosis needed for medical necessity.
   - All data clearly labeled SYNTHETIC. No real PHI.

B. INGESTION: typed loaders per source that normalize every item into the canonical metadata model. Store raw file pointer as source_uri for lineage.

C. METADATA EXTRACTION: parse out document_type, policy_id, effective_date, expiry_date, procedure_codes (CPT), diagnosis_codes (ICD-10), payer, plan_id, owner.

D. DATA-QUALITY RULE ENGINE (section 5.4) — pluggable rules, each returns pass/warn/quarantine + message:
   - completeness (missing effective_date, payer/plan, empty procedure_codes)
   - validity (malformed dates, invalid NPI checksum, bad CPT/ICD pattern)
   - timeliness (expiry_date < today => expired)
   - uniqueness (duplicate NPI; duplicate policy_id w/ different content)
   - consistency/conflict (two ACTIVE policies, same payer+plan+CPT, opposite PA requirement => conflict)
   - patient context (bundle missing required diagnosis)
   Quarantined records are stored but flagged dq_status='quarantined' and EXCLUDED from later retrieval. Produce a DQ report (JSON + console summary) per ingestion run.

E. TESTS: write pytest tests proving each DQ rule fires on the seeded defects (expired caught, conflict caught, duplicate caught, missing-date caught, invalid NPI caught).

When done: run the ingestion, show me the DQ report summary, run the tests, and confirm every seeded defect was caught. Then stop.
```

---

### ▶ PROMPT 3 — Knowledge layer (chunk, embed, store, lineage) *(model: Auto)*

```
Continue MediGovern RAG. Implement PHASE 3 (Knowledge layer) from the plan (section 5.5 first half, 5.6 lineage).

Tasks:
1. Chunk the PASSED (non-quarantined) documents sensibly (preserve policy clause boundaries where possible).
2. Generate embeddings via the swappable provider interface and store vectors in pgvector.
3. Maintain a STRUCTURED metadata index alongside vectors so retrieval can pre-filter by plan_id, payer, CPT/ICD, effective_date window, and dq_status.
4. Store lineage pointers: every chunk links back to its document_id and source_uri.
5. Add an `ingest_and_index` command that runs the full path: load -> extract -> DQ gate -> chunk -> embed -> store.

Constraints: quarantined records must NOT be embedded. After finishing, run the full index build and report counts: docs ingested, passed, quarantined, chunks embedded. Then stop.
```

---

### ▶ PROMPT 4 — Retrieval, generation, citations, audit packet *(model: Sonnet)*

```
Continue MediGovern RAG. Implement PHASE 4 (Retrieval + Generation + Audit) from the plan (sections 5.5, 5.6) and expose it via FastAPI.

A. RETRIEVAL (section 5.5):
   - Pre-filter on metadata BEFORE semantic search: plan_id, payer, CPT, effective_date <= today <= expiry_date, dq_status='passed'.
   - Semantic search top-k within the filtered set.
   - Assemble context with explicit source attributions (policy_id + clause).

B. GENERATION:
   - Strict prompt template: the answer MUST cite policy_id + clause, and MUST state what it could NOT find.
   - Confidence score in 3 bands (High/Medium/Low) derived from retrieval scores + whether a single authoritative in-effect policy was found + DQ status of supporting docs.
   - ABSTAIN path: if no in-scope policy OR conflicting active policies exist, do NOT guess — return "needs human review" with the reason, and surface the conflict.

C. AUDIT PACKET (section 5.6): for every answered question, build a structured audit packet (JSON + a rendered HTML) containing: the question, timestamp, role, model+version, metadata filters applied, every retrieved chunk with policy_id/clause/effective dates/source_uri, DQ status of each supporting doc, final answer, citations, confidence band, and missing-data findings. Write an append-only audit_log row per query.

D. API: FastAPI endpoint `POST /ask` that accepts {question, plan_id?, payer?, cpt?} and returns {answer, citations, confidence, missing_data, audit_packet_id}. Add `GET /audit/{id}` to fetch a packet. Keep Swagger /docs working.

E. EVAL: add the 5 demo questions from section 2 as a small test set and a script that runs them and prints answer + confidence + whether citations are present. Include the conflict question and the expired-policy case.

When done: start the API, run the 5 demo questions through /ask, and show me the outputs (especially that the conflicting-rules question ABSTAINS and the expired policy is excluded). Then stop.
```

---

### ▶ PROMPT 5 — Hardening, deploy, glue for the front-end *(model: Sonnet)*

```
Continue MediGovern RAG. Prepare it for a front-end and a demo.

Tasks:
1. Add CORS to FastAPI so a Lovable/Supabase front-end can call it.
2. Add list endpoints the dashboard needs: GET /policies (catalog with metadata + lineage), GET /quarantine (quarantined records + reasons), GET /audit (recent query history).
3. Seed the DB on startup if empty (run ingest_and_index) so a fresh deploy is demo-ready.
4. Write a Dockerfile and a one-command deploy guide for Railway OR Render (free tier). Include the exact steps and required env vars.
5. Update README with: architecture summary, how to run locally, how to deploy, the 5 demo questions, and a "Built with AI" section noting the design decisions I made (metadata model, DQ rules, abstain-on-conflict, audit packet) vs. what AI agents implemented.

When done: give me the deployed base URL steps and the list of endpoints with example requests. Then stop.
```

---

# PART B — LOVABLE (front-end / governance dashboard)

You have **210 credits** — plenty. Batch your asks so you don't burn credits on tiny tweaks. Paste **PROMPT 6** as your first Lovable message, then iterate.

### ▶ PROMPT 6 — Build the governance dashboard *(Lovable)*

```
Build a healthcare data-governance dashboard called "MediGovern RAG" — clean, professional, enterprise SaaS look (neutral palette, clear typography, sidebar nav). It is a front-end for an existing REST API; I will give you the base URL.

Pages / features:
1. Overview dashboard: cards showing ingestion stats (docs ingested, passed, quarantined), and a chart of DQ pass/warn/quarantine counts.
2. Policy Catalog: searchable, filterable table of policies pulled from GET /policies — columns: policy_id, payer, plan, CPT codes, effective_date, expiry_date, dq_status. Clicking a row shows metadata + lineage (source_uri).
3. Quarantine Queue: table from GET /quarantine showing each flagged record and the DQ reason (expired, conflict, duplicate, missing date, invalid NPI).
4. Ask (Q&A): a prompt box with the 5 example questions as quick-select chips:
   - "Does CPT 70553 require prior authorization for this plan?"
   - "Which policy supports the denial reason?"
   - "What patient data is missing before submitting authorization?"
   - "Are there conflicting coverage rules for this procedure?"
   - "Show the lineage for this recommendation."
   On submit, call POST /ask and render: the answer, citations (policy_id + clause), a confidence badge (High/Medium/Low), and a "missing data" list. If the response says human-review/abstain, show that prominently.
5. Audit Viewer: given an audit_packet_id, call GET /audit/{id} and render the full packet (filters applied, retrieved chunks with sources, DQ status, final answer) with a "Download" button.

Technical:
- Use a config value for the API base URL so I can point it at my deployed backend.
- Use Supabase for auth (email login) so it feels enterprise.
- Handle loading and error states gracefully.

Start with the layout + Overview + Ask pages first; we'll refine the others next.
```

**Follow-up Lovable messages (one feature each, to save credits):**
- `Now build the Policy Catalog page with row-click detail drawer.`
- `Now build the Quarantine Queue page.`
- `Now build the Audit Viewer page with download.`
- `Connect everything to my API base URL: <PASTE URL>. Test the Ask page end to end.`

---

# PART C — CLAUDE COWORK (showcase only — run Friday)

Save your remaining Cowork usage for this. Low token cost, high portfolio value.

### ▶ PROMPT 7 — Showcase package *(Claude Cowork)*

```
I built "MediGovern RAG", a healthcare prior-authorization data-governance RAG pipeline (FHIR-aware ingestion, metadata-driven retrieval, data-quality gating with quarantine, abstain-on-conflict, and auditable policy citations / audit packets), aligned to the CMS-0057-F prior authorization rule. Built with Cursor (backend) + Lovable (dashboard), designed by me.

Produce a showcase package:
1. A polished README "elevator pitch" + "How it works" + "Built with AI" section (what I designed vs. what agents implemented).
2. A LinkedIn post (hook + what it does + why it matters for CMS-0057-F 2026/2027 deadlines + a soft CTA). Confident, senior, not hypey.
3. A 3-4 minute demo video script walking through the 5 demo questions, including the moment it ABSTAINS on conflicting policies and excludes the expired policy.
4. A short newsletter section version of the above.

Keep it concrete and grounded in what the system actually does. Emphasize governance + auditability as the differentiator vs "chat with PDF".
```

---

# Run order (the whole thing)

1. **Cursor** Prompt 1 → commit
2. **Cursor** Prompt 2 → commit (confirm all DQ defects caught)
3. **Cursor** Prompt 3 → commit
4. **Cursor** Prompt 4 → commit (confirm 5 questions + abstain works)
5. **Cursor** Prompt 5 → deploy backend, grab the URL
6. **Lovable** Prompt 6 (+ follow-ups) → connect to the URL
7. **Cowork** Prompt 7 → ship the story

## Tips to hit Friday
- Commit after every prompt so you can roll back cleanly.
- If a prompt's output is too big or errors, tell Cursor: *"that failed with <error> — fix just that, don't refactor the rest."*
- Keep scope to **CPT 70553 + 2 plans + ~12 policies**. Resist expanding.
- If you fall behind on the UI, demo from FastAPI `/docs` + the audit-packet JSON — the governance logic is the star.
```
