# MediGovern RAG — Prior Authorization & Policy Intelligence Pipeline
### Implementation Plan (Build-Spec Depth)

**Author:** Ramachandran Balasubrahmanian
**Date:** June 16, 2026
**Purpose:** A complete, hand-off-ready build plan for a healthcare prior-authorization + data-governance RAG pipeline — structured the way a *matured enterprise data platform* organization would actually run it (Discovery → Design → Build → Govern → Showcase). Designed to be executed with Codex, Antigravity, Claude Code, or Claude Cowork, with a Lovable front-end as the showcase layer.

> This document is a **plan only**. No code is built here. Hand sections 4–7 to your coding agent as a spec.

---

## 0. How to read this document

This plan has two layers running in parallel, because you asked for both:

1. **The portfolio/showcase layer** — what *you* build to prove the concept and put it on LinkedIn/GitHub/your newsletter. Cheap, fast, synthetic data only.
2. **The enterprise layer** — how a *matured organization* (a payer or large provider with an existing data platform) would take this exact idea through a real Discovery → Production lifecycle, with governance, security, and compliance.

Wherever it matters, each section flags **[SHOWCASE]** vs **[ENTERPRISE]** so you can pitch the difference. Being able to articulate *both* is what makes this look senior rather than like a student project.

---

## 1. The problem, restated for an enterprise audience

Healthcare payers and providers must make prior authorization (PA) and coverage decisions that are **fast, accurate, and auditable**. Today the inputs to those decisions — payer policy documents, clinical guidelines, benefit plan rules, provider directories, and patient clinical records — are fragmented across systems, inconsistently governed, and hard to trace back to a source of truth.

This is now a **regulatory deadline problem**, not just an efficiency problem:

- The **CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F)**, released January 17, 2024, requires impacted payers (Medicare Advantage, Medicaid, CHIP, and federal-exchange QHP issuers) to accelerate PA decisions and stand up standardized FHIR APIs.
- **By January 1, 2026:** impacted payers must accept electronic PA requests and respond within mandated timeframes — **72 hours for expedited** and **7 calendar days for standard** requests — and report PA metrics.
- **By January 1, 2027:** payers must have fully implemented four FHIR APIs — **Prior Authorization API, Provider Access API, Patient Access API, and Payer-to-Payer API.**

So the business case writes itself: organizations need a governed, traceable knowledge layer that can answer "does this require PA, under which policy, with what supporting evidence, and is anything missing?" — fast enough to hit a 72-hour clock and auditable enough to survive a CMS or appeals review.

**Your positioning line:** *"A healthcare data-governance RAG pipeline for prior-authorization intelligence — FHIR-aware ingestion, metadata-driven retrieval, data-quality gating, and auditable policy citations."*

---

## 2. Product definition — MediGovern RAG

**Name:** MediGovern RAG — Prior Authorization & Policy Intelligence Pipeline

**One-line:** Ask a plain-English PA question, get an answer with citations, a confidence score, a list of missing data, and a downloadable **audit packet** proving exactly which policy and data elements supported the recommendation.

**Core capabilities (MVP):**

1. **Ingest** payer policy PDFs, medical/clinical guidelines, plan benefit documents, synthetic FHIR patient bundles, provider directory data, and claims-like CSV records.
2. **Extract metadata** per document/record: document type, policy ID, effective/expiry date, procedure (CPT/HCPCS) code, diagnosis (ICD-10) code, payer, plan, source system, data owner.
3. **Run data-quality (DQ) checks:** missing effective dates, expired policies, duplicate providers, conflicting plan rules, incomplete patient context.
4. **Embed + store** chunks in a vector DB with a parallel **structured metadata index**.
5. **Metadata-filtered retrieval** — filter by plan/payer/code/effective-date *before* semantic search.
6. **Answer generation** with inline citations and a calibrated confidence score.
7. **Audit packet** — a generated artifact listing every policy clause, guideline, and data element that supported the answer, plus lineage.

**Five demo questions to anchor the build (and the demo video):**

- "Does CPT 70553 require prior authorization for this plan?"
- "Which policy supports the denial reason?"
- "What patient data is missing before submitting authorization?"
- "Are there conflicting coverage rules for this procedure?"
- "Show the lineage for this recommendation."

**Explicit non-goals (state these — it signals maturity):** no real PHI, not a clinical decision-support device, not making the final medical determination, no payer system of record integration in MVP. It is a **decision-support and governance** layer.

---

## 3. Reference architecture

```
SOURCES                INGESTION            GOVERNANCE GATE          KNOWLEDGE LAYER        SERVING
─────────              ─────────            ───────────────          ───────────────        ───────
Policy PDFs       ┐                    ┌─ Metadata extraction    ┌─ Chunking            ┌─ Metadata-filtered
Clinical guides   │                    │   (type, IDs, dates,    │   + embeddings       │   retrieval
Plan benefits     ├─►  Ingestion   ──► │    CPT/ICD, payer,      ├─► Vector DB +     ──►├─ Answer gen w/
FHIR bundles      │     pipeline       │    plan, owner)         │   metadata index     │   citations + conf.
Provider dir      │   (loaders +       │                         │                      │
Claims CSV        ┘    validators)     └─ Data-quality checks    └─ Lineage capture     └─ Audit packet +
                                          (gate: pass/quarantine)                           governance dashboard
                                                                                            
                                              ▼                                              ▼
                                    Quarantine / DQ report                      Audit log (immutable)
```

**Layer-by-layer:**

- **Sources:** all synthetic for the showcase (see §5.3). Enterprise swaps in governed feeds.
- **Ingestion pipeline:** typed loaders per source; normalize into a common document/record schema.
- **Governance gate:** metadata extraction + DQ validation. Records that fail critical checks are **quarantined**, not silently embedded — this is the single most "enterprise" thing in the build and your biggest differentiator vs "chat with PDF."
- **Knowledge layer:** chunk, embed, store. Keep structured metadata in a queryable index alongside vectors so retrieval can pre-filter.
- **Serving:** retrieval → generation → citation → audit packet. Every answer writes to an immutable audit log.

---

## 4. The Discovery Phase (how a matured enterprise starts) **[ENTERPRISE]**

A mature data-platform org never starts by coding. Discovery is a **time-boxed (typically 3–6 week)** phase whose job is to de-risk the build and produce decision-ready artifacts. This is the section that makes you sound like a Data Management / AI Governance leader rather than a developer.

### 4.1 Discovery objectives

- Define the precise decision the system supports and who is accountable for it.
- Map the data landscape: sources, owners, sensitivity, quality, lineage.
- Establish the governance, security, and regulatory guardrails up front.
- Produce a scoped MVP with measurable success criteria and a cost envelope.

### 4.2 Discovery workstreams & activities

1. **Business & regulatory framing**
   - Stakeholder interviews: utilization management, clinical policy, compliance, provider relations, data platform/engineering.
   - Map the target workflow to CMS-0057-F obligations and the 72-hour / 7-day clocks.
   - Define the decision boundary: assist vs. automate. (MVP = assist.)

2. **Data discovery & profiling**
   - Inventory candidate sources; classify each by sensitivity (PHI/PII), owner, refresh cadence, format, and system of record.
   - Profile data quality: completeness, validity, uniqueness, timeliness, consistency.
   - Identify authoritative source for each entity (policy, plan, provider, member, code set).

3. **Governance & metadata design**
   - Define the metadata model and a business glossary (policy, plan, benefit, PA, medical necessity, lineage, etc.).
   - Map to a framework — **DAMA-DMBOK** knowledge areas (Data Quality, Metadata, Reference & Master Data, Data Security, Data Architecture) — and cite it in your deck.
   - Decide ownership/stewardship (RACI) for each domain.

4. **Security, privacy & compliance**
   - HIPAA posture, PHI handling, de-identification strategy, access-control model (RBAC/ABAC), data residency, audit/retention requirements.
   - "AI guardrails": hallucination risk, human-in-the-loop requirement, model/version disclosure on every answer.

5. **Technical landscape & integration**
   - FHIR server / EHR integration points; terminology services (CPT, HCPCS, ICD-10, SNOMED, LOINC, value sets).
   - Target platform fit (existing lakehouse, vector store standard, model hosting — cloud vs. on-prem vs. VPC).

6. **Solution shaping & MVP scoping**
   - Define MVP scope, success metrics, and a thin-slice use case (one procedure family, one or two plans).
   - Build vs. buy analysis for each component (vector DB, orchestration, model).

### 4.3 Discovery **outcomes** (the deliverables you should be able to name)

A clean Discovery produces these artifacts — list them on a slide; they double as your portfolio evidence:

| # | Outcome / Artifact | What it contains |
|---|--------------------|------------------|
| 1 | **Problem & decision charter** | The exact PA decision, accountable owner, success metrics, regulatory drivers (CMS-0057-F). |
| 2 | **Source inventory & data-sensitivity register** | Every source, owner, classification (PHI/PII), format, refresh cadence, system of record. |
| 3 | **Data-quality baseline report** | Profiling results + the DQ rules the pipeline must enforce, with thresholds. |
| 4 | **Metadata model & business glossary** | The canonical metadata schema (§5.2) + defined terms, mapped to DAMA-DMBOK. |
| 5 | **Governance operating model (RACI)** | Stewardship, ownership, approval gates, change control. |
| 6 | **Security & compliance guardrail spec** | HIPAA controls, de-id approach, RBAC/ABAC model, audit & retention policy, AI-use guardrails. |
| 7 | **Reference architecture & build-vs-buy decisions** | The §3 diagram with chosen technologies and rationale. |
| 8 | **MVP scope + success criteria + KPIs** | Thin-slice use case, acceptance tests, target metrics (§9). |
| 9 | **Risk register & RAID log** | Risks, assumptions, issues, dependencies — incl. hallucination, data drift, expired-policy risk. |
| 10 | **Cost model & roadmap** | Phased plan, cost envelope (§10), and a go/no-go recommendation. |

**Discovery exit gate:** a go/no-go review where stewards, security, and the platform owner sign off on outcomes 1–10. Nothing gets built before this gate clears. *Saying this sentence in an interview is worth a lot.*

---

## 5. Build phase — detailed, agent-ready spec

This is the part you hand to Codex / Claude Code / Antigravity. Keep it stack-agnostic where possible; suggested defaults in brackets.

### 5.1 Recommended stack (showcase defaults)

- **Language/runtime:** Python 3.11 [orchestration + pipeline], TypeScript/React [front-end via Lovable].
- **Orchestration:** a lightweight DAG or simple sequential pipeline (LangChain/LlamaIndex *or* hand-rolled — hand-rolled reads as more "you understand it").
- **Vector DB:** start with **pgvector on Postgres** (one DB for vectors *and* structured metadata = simpler lineage + filtering). Alternatives: Chroma (local), Qdrant/Weaviate (scale).
- **Embeddings + LLM:** any provider you already use (OpenAI/Anthropic/local). Keep the model behind an interface so it's swappable.
- **API layer:** FastAPI.
- **Front-end / showcase:** **Lovable** (see §6) calling your FastAPI backend, OR fully inside Lovable + Supabase (see §6.2).
- **Storage:** object storage for raw docs + audit packets; Postgres for metadata, DQ results, audit log.

### 5.2 Canonical metadata model (define once, enforce everywhere)

Every ingested artifact carries a metadata record. This is your governance backbone:

```
document_id            (uuid)
source_system          (enum: policy_pdf | guideline | plan_benefit | fhir | provider_dir | claims)
document_type          (enum: medical_policy | clinical_guideline | benefit_doc | patient_bundle | provider_record | claim)
title
policy_id              (nullable)
payer
plan_id
effective_date         (date)
expiry_date            (date, nullable)
procedure_codes        (array: CPT/HCPCS)
diagnosis_codes        (array: ICD-10)
data_owner / steward
source_uri             (lineage pointer to raw file/record)
ingested_at, version
sensitivity            (enum: synthetic | pii | phi)
dq_status              (enum: passed | warning | quarantined)
dq_findings            (array of rule results)
```

### 5.3 Synthetic data plan **[SHOWCASE — critical, do this right]**

**Never use real PHI.** Generate or use openly-licensed synthetic data so you can publish freely:

- **FHIR patient data:** use **Synthea** (open-source synthetic patient generator) to produce FHIR R4 bundles — realistic, fully synthetic, publishable.
- **Policy PDFs / guidelines:** write 8–15 short synthetic "payer medical policy" PDFs yourself (or have the agent generate them) covering a handful of procedures (e.g., MRI brain CPT 70553, sleep study, advanced imaging). Deliberately seed them with governance defects: one expired policy, two with conflicting rules for the same CPT, one missing an effective date.
- **Provider directory:** synthetic CSV with deliberate duplicates and a few invalid NPIs.
- **Claims-like records:** synthetic CSV linking members ↔ CPT ↔ plan ↔ outcome.
- **Code sets:** use public CPT/ICD-10 *descriptions* sparingly and note licensing (CPT is AMA-licensed — for a public demo, use a small illustrative subset and label it as such).

> Seeding deliberate defects is the whole point: your DQ layer needs something to *catch* on camera.

### 5.4 Data-quality rule set (MVP)

Implement as a pluggable rule engine; each rule returns pass/warn/quarantine + a message:

- **Completeness:** missing effective_date, missing payer/plan, empty procedure_codes on a policy doc.
- **Validity:** malformed dates, invalid NPI checksum, unknown CPT/ICD pattern.
- **Timeliness:** `expiry_date < today` → expired policy (quarantine or flag).
- **Uniqueness:** duplicate provider records (same NPI), duplicate policy_id with different content.
- **Consistency/conflict:** two active policies for the same payer+plan+CPT with opposite PA requirements → conflict flag.
- **Patient context:** patient bundle missing diagnosis needed to evaluate medical necessity.

Output: a **DQ report** per ingestion run + per-record `dq_status`. Quarantined records are excluded from retrieval but visible in the dashboard.

### 5.5 Retrieval & generation design

1. **Pre-filter** on metadata (plan_id, payer, CPT, effective_date ≤ today ≤ expiry_date, dq_status = passed) — this is "metadata-driven retrieval," your headline differentiator.
2. **Semantic search** within the filtered set (top-k chunks).
3. **Re-rank** (optional) and assemble context with explicit source attributions.
4. **Generate** the answer with a strict prompt template that *must* cite policy_id + clause and *must* report what it could not find.
5. **Confidence score:** derive from retrieval scores + whether a single authoritative policy was found + DQ status of supporting docs. Calibrate to 3 bands (High/Medium/Low) — don't over-engineer.
6. **Refusal/abstain path:** if no policy in scope or conflicting policies, the system says so and routes to human review rather than guessing.

### 5.6 Audit packet & lineage

For each answered question, generate a structured **audit packet** (JSON + rendered PDF/HTML) containing:

- The question, timestamp, user/role, model + version used.
- The metadata filters applied.
- Every retrieved chunk with its policy_id, clause, effective dates, source_uri (lineage).
- The DQ status of each supporting document.
- The final answer, citations, confidence band, and any "missing data" findings.
- A lineage trail: answer → chunks → documents → source files.

Write an **immutable audit log** entry (append-only table) per query. This is what lets you say "auditable" with a straight face.

### 5.7 Governance dashboard (the visual that sells it)

A simple dashboard (this is mostly what Lovable builds) showing:

- Ingestion runs and DQ pass/warn/quarantine counts.
- A searchable catalog of policies with metadata + lineage.
- Quarantine queue with reasons.
- Query history with audit-packet download.
- The Q&A interface itself (the 5 demo questions).

---

## 6. Lovable — can it build this, and how much will it cost?

### 6.1 Short answer
**Yes — Lovable can build the front-end and a thin full-stack version of this**, and it's a strong choice for the *showcase* layer specifically: the governance dashboard, the policy catalog, the Q&A UI, and the audit-packet viewer. Lovable generates React/Tailwind front-ends and can wire up a **Supabase** backend (Postgres + auth + storage), which conveniently is *also* where your **pgvector** store and metadata index can live.

**What Lovable is great for here:** the UI, auth, the dashboard, CRUD over your metadata/catalog, calling your RAG API, and rendering audit packets.

**What you'll still own outside Lovable (or drive via Codex/Claude Code):** the ingestion + metadata-extraction + DQ pipeline, embeddings/retrieval logic, and the LLM orchestration. You can host that as a small FastAPI service (or as Supabase edge functions) and have Lovable's front-end call it. Trying to make Lovable do the heavy data-engineering is the wrong tool; let it own the experience layer.

**Recommended split:**
- **Lovable + Supabase** → UI, auth, metadata catalog, dashboard, audit-packet viewer, Q&A screen. Vector store in Supabase/pgvector.
- **Codex / Claude Code** → the Python ingestion/DQ/retrieval/orchestration service + synthetic-data generation + tests.

### 6.2 Lovable pricing (verified, June 2026)

Lovable's published plans:

| Plan | Price | What you get |
|------|-------|--------------|
| **Free** | **$0** | ~5 daily credits, capped at ~30/month; temporary free Cloud hosting credit (through Q1 2026). Good for a first prototype. |
| **Pro** | **$25/month** | 100 monthly credits (roll over while subscribed) + 5 daily bonus credits, up to ~150 total/month. Custom domains, more usage. |
| **Business** | **$50/month** | 100 credits **plus** SSO and a security center — relevant if you want to *talk* enterprise. |
| **Enterprise** | Custom (contact sales) | SSO, dedicated support, higher limits. |

How credits burn: **one credit per message to Lovable's AI** — simple styling tweaks ~0.5 credit, complex features (e.g., auth) ~1.2 credits. So cost scales with how much iterating you do, not with users.

**Realistic Lovable spend for your showcase:** start **Free** to prototype; expect to need **Pro ($25/mo) for 1–2 months** to finish a polished, demo-able app — call it **$25–$75 total**. Business ($50/mo) only if you specifically want SSO/security-center talking points for the portfolio narrative.

> Pricing and credit mechanics change often — confirm on Lovable's pricing page before subscribing. Sources are listed at the end.

---

## 7. Execution roadmap (phased, with agent assignments)

**Phase 0 — Discovery (this doc + §4 artifacts).** No code. Produce outcomes 1–10. *You + Claude (Cowork) for the writeup.*

**Phase 1 — Foundations (Week 1).**
- Stand up repo, Postgres+pgvector (or Supabase), object storage, FastAPI skeleton, secrets.
- Generate synthetic data with Synthea + author the defective policy PDFs.
- *Agent: Codex / Claude Code.*

**Phase 2 — Ingestion + Governance gate (Weeks 1–2).**
- Loaders per source → common schema → metadata extraction → DQ rule engine → quarantine logic → DQ report.
- *Agent: Codex / Claude Code.* Tests for every DQ rule.

**Phase 3 — Knowledge layer (Week 2).**
- Chunk, embed, store; build metadata index; lineage pointers.
- *Agent: Codex / Claude Code.*

**Phase 4 — Retrieval + generation + audit (Weeks 3).**
- Metadata pre-filter → semantic search → cited answer → confidence band → audit packet → immutable audit log.
- *Agent: Codex / Claude Code.*

**Phase 5 — Front-end / dashboard (Week 3–4).**
- Lovable builds the dashboard, catalog, Q&A UI, audit-packet viewer; wire to the API.
- *Agent: Lovable (+ Codex for glue).*

**Phase 6 — Hardening + showcase (Week 4).**
- Evaluation harness (the 5 demo questions as a test set), README, architecture diagram, 3–4 min demo video, LinkedIn post + newsletter writeup.
- *Agent: Claude (Cowork) for narrative + Codex for the eval harness.*

> Solo, part-time, this is a **~4–5 week** build. The Discovery writeup is what differentiates you, so don't shortcut it.

---

## 8. How a matured enterprise would take this to production **[ENTERPRISE]**

Show that you know the gap between a demo and production — name these explicitly:

- **Data:** replace synthetic with governed feeds via a FHIR server; terminology services for CPT/HCPCS/ICD-10/SNOMED/LOINC and value sets; master/reference data management for providers, plans, members.
- **Security/compliance:** HIPAA controls, PHI handling + de-identification, RBAC/ABAC, encryption at rest/in transit, full audit & retention, BAA with any model vendor or a privately-hosted model in a VPC.
- **Governance:** stewardship operating model, change control on policies, a policy "effective-dating" workflow, model governance (versioning, eval gates, drift monitoring, human-in-the-loop sign-off on every PA recommendation).
- **Scale/reliability:** orchestration (Airflow/Dagster), CI/CD, observability, SLAs aligned to the 72-hour/7-day clocks, DR.
- **Integration:** the four CMS FHIR APIs (Prior Auth, Provider Access, Patient Access, Payer-to-Payer) and EHR/UM-system hooks.
- **Assurance:** clinical validation, bias/fairness review, and an audit trail that survives CMS reporting and member appeals.

---

## 9. Success metrics / KPIs (put these on a slide)

- **Decision latency:** time-to-recommendation (target: seconds; context: the regulatory clock is 72h/7d).
- **Citation coverage:** % of answers with a valid, in-effect policy citation (target ~100%).
- **Groundedness / hallucination rate:** % of answers fully supported by retrieved sources (eval set).
- **DQ catch rate:** % of seeded defects correctly quarantined/flagged.
- **Conflict detection:** % of seeded conflicting-policy cases surfaced.
- **Abstention correctness:** system abstains/routes-to-human when it should.
- **Auditability:** % of answers with a complete, downloadable audit packet (target 100%).

---

## 10. Cost summary

### 10.1 Showcase budget **[SHOWCASE]**

| Item | Cost |
|------|------|
| Lovable (Free → Pro for 1–2 months) | **$0–$75** |
| LLM + embeddings API usage (synthetic data, light dev) | **$10–$50** |
| Hosting/DB — Supabase free tier or a small VM | **$0–$25/mo** (often $0 on free tiers) |
| Synthea, Postgres/pgvector, FastAPI, your coding agents you already pay for | **$0** |
| Domain name (optional, nicer for portfolio) | **~$12/yr** |
| **Total realistic out-of-pocket** | **≈ $25–$150** to a polished, public demo |

You can genuinely ship the showcase for **under ~$100** if you stay on free/low tiers and keep LLM calls modest.

### 10.2 Enterprise budget **[ENTERPRISE]** (order-of-magnitude, for the narrative)

This is what you'd *quote in Discovery*, not spend yourself. Useful to show you can size a program:

| Item | Indicative range |
|------|------------------|
| Discovery phase (3–6 wks, small team) | $40k–$120k |
| MVP/pilot build (governed data, security, 1 use case) | $150k–$400k |
| Production hardening + CMS FHIR API integration | $500k–$1.5M+ |
| Run cost (infra, model hosting in VPC, monitoring, stewardship) | $15k–$60k+/month |

*Ranges vary widely by org size, vendor vs. build, and whether they already run a data platform. Present these as planning envelopes, not quotes.*

---

## 11. Why this lands on LinkedIn / GitHub / your newsletter

- It maps to a **real, dated regulatory mandate** (CMS-0057-F, 2026/2027) — not a toy problem.
- It demonstrates **data governance** (metadata, DQ, lineage, access control, auditability), which is rarer and more senior than "RAG over PDFs."
- The **audit packet + governance dashboard** are screenshot-ready proof.
- You can publish it freely because it's **100% synthetic**.
- You can tell the **Discovery-to-Production** story, which is a leadership signal.

**Suggested post hook:** *"Most RAG demos answer questions. This one refuses to answer when the policy is expired, the data is missing, or two coverage rules conflict — and hands you an audit packet either way. Here's how I built a healthcare prior-auth governance pipeline aligned to CMS-0057-F."*

---

## 12. Sources

- CMS — Interoperability and Prior Authorization Final Rule (CMS-0057-F): https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/policies-regulations/cms-interoperability-prior-authorization-final-rule-cms-0057-f
- CMS-0057-F deadlines & API requirements (summary): https://innovaccer.com/resources/blogs/cms-0057-prior-authorization-rule-requirements-deadlines-apis-and-operational-impact
- HL7 FHIR Overview: https://hl7.org/fhir/overview.html
- DAMA-DMBOK (Data Management Body of Knowledge): https://dama.org/learning-resources/dama-data-management-body-of-knowledge-dmbok/
- Data Quality Challenges in RAG (arXiv): https://arxiv.org/abs/2510.00552
- Synthea synthetic patient generator: https://synthetichealth.github.io/synthea/
- Lovable pricing (2026 guide): https://www.eesel.ai/blog/lovable-pricing
- Lovable pricing (plans & credits): https://www.websitebuilderexpert.com/vibe-coding/lovable-pricing/
