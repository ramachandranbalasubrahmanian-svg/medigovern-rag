"""Answer generation with strict citation template, confidence bands, and abstain path."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.providers import get_llm_provider
from pipeline.retrieval.retriever import RetrievalResult, RetrievedChunk


SYSTEM_PROMPT = """You are MediGovern RAG, a healthcare prior-authorization decision-support assistant.

Rules you MUST follow in every response:
1. ONLY use information from the provided policy chunks. Do NOT add clinical or legal knowledge.
2. You MUST cite the policy_id and section label for every claim you make.
3. You MUST state what information you could NOT find.
4. Use plain, professional language. No disclaimers beyond the required governance notice.
5. End every answer with: "⚠ GOVERNANCE: This is decision-support only. Final authorization requires human clinical review."
"""

ANSWER_TEMPLATE = """Based on the provided policy documents, answer the following prior-authorization question.

QUESTION: {question}

RETRIEVED POLICY CONTEXT:
{context}

Instructions:
- Answer directly based ONLY on the above context.
- Cite each policy by [policy_id — section] for every factual claim.
- List any required information that is MISSING from the context.
- Do not guess. If the answer is not supported, say so.
"""

CONFLICT_TEMPLATE = """The following prior-authorization question cannot be answered automatically because active policies contain conflicting requirements.

QUESTION: {question}

CONFLICT DETECTED:
{conflict_detail}

CONFLICTING POLICY CHUNKS:
{context}

This case requires HUMAN REVIEW. Do not provide a PA recommendation.
Summarize the conflict clearly for the reviewer.
"""


@dataclass
class Citation:
    policy_id: str | None
    section_label: str | None
    source_uri: str
    effective_date: str | None
    expiry_date: str | None
    dq_status: str
    chunk_text_snippet: str  # first 200 chars


@dataclass
class GenerationResult:
    answer: str
    confidence: str            # High / Medium / Low / ABSTAIN
    confidence_rationale: str
    citations: list[Citation] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    abstained: bool = False
    abstain_reason: str = ""


def generate_answer(retrieval: RetrievalResult) -> GenerationResult:
    """Generate a cited answer or ABSTAIN based on retrieval result."""

    # ABSTAIN: no policy found
    if retrieval.no_policy_found or not retrieval.chunks:
        return GenerationResult(
            answer=(
                "No in-scope policy was found for this question with the provided filters. "
                "This case requires human review."
            ),
            confidence="ABSTAIN",
            confidence_rationale="No relevant policy found in the knowledge base.",
            abstained=True,
            abstain_reason="No in-scope policy found.",
        )

    # ABSTAIN: conflicting active policies
    if retrieval.has_conflict:
        context = _format_context(retrieval.chunks)
        llm = get_llm_provider()
        summary = llm.generate(
            CONFLICT_TEMPLATE.format(
                question=retrieval.query,
                conflict_detail=retrieval.conflict_detail,
                context=context,
            ),
            system=SYSTEM_PROMPT,
        )
        citations = _build_citations(retrieval.chunks)
        return GenerationResult(
            answer=f"⛔ NEEDS HUMAN REVIEW — Conflicting policies detected.\n\n{summary}",
            confidence="ABSTAIN",
            confidence_rationale=retrieval.conflict_detail,
            citations=citations,
            abstained=True,
            abstain_reason=retrieval.conflict_detail,
        )

    # Normal path: generate cited answer
    context = _format_context(retrieval.chunks)
    llm = get_llm_provider()
    answer_text = llm.generate(
        ANSWER_TEMPLATE.format(question=retrieval.query, context=context),
        system=SYSTEM_PROMPT,
    )

    citations = _build_citations(retrieval.chunks)
    missing = _extract_missing(answer_text)
    confidence, rationale = _score_confidence(retrieval.chunks, answer_text)

    return GenerationResult(
        answer=answer_text,
        confidence=confidence,
        confidence_rationale=rationale,
        citations=citations,
        missing_data=missing,
        abstained=False,
    )


def _format_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        label = c.section_label or "General"
        policy = c.policy_id or "UNKNOWN"
        eff = str(c.effective_date) if c.effective_date else "N/A"
        exp = str(c.expiry_date) if c.expiry_date else "No expiry"
        score = f"{c.similarity_score:.3f}"
        parts.append(
            f"[{i}] Policy: {policy} | Section: {label} | "
            f"Effective: {eff} | Expiry: {exp} | DQ: {c.dq_status} | Score: {score}\n"
            f"{c.chunk_text}"
        )
    return "\n\n---\n\n".join(parts)


def _build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    seen: set[str] = set()
    citations = []
    for c in chunks:
        key = f"{c.policy_id}:{c.section_label}"
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                policy_id=c.policy_id,
                section_label=c.section_label,
                source_uri=c.source_uri,
                effective_date=str(c.effective_date) if c.effective_date else None,
                expiry_date=str(c.expiry_date) if c.expiry_date else None,
                dq_status=c.dq_status,
                chunk_text_snippet=c.chunk_text[:200],
            )
        )
    return citations


def _extract_missing(answer_text: str) -> list[str]:
    """Best-effort extraction of 'missing data' sentences from generated answer."""
    missing = []
    lower = answer_text.lower()
    for line in answer_text.splitlines():
        line_l = line.lower()
        if any(
            kw in line_l
            for kw in ("not found", "missing", "not available", "could not find",
                       "no information", "not provided", "unavailable")
        ):
            stripped = line.strip(" -•*")
            if stripped:
                missing.append(stripped)
    return missing


def _score_confidence(
    chunks: list[RetrievedChunk], answer_text: str
) -> tuple[str, str]:
    """Derive confidence band from retrieval signal."""
    if not chunks:
        return "Low", "No supporting documents retrieved."

    top_score = chunks[0].similarity_score
    all_passed = all(c.dq_status == "passed" for c in chunks)

    # Count unique authoritative policies (medical_policy type) that are in-scope
    policy_ids = {c.policy_id for c in chunks if c.policy_id and c.document_type == "medical_policy"}
    single_authoritative = len(policy_ids) == 1

    if top_score >= 0.85 and single_authoritative and all_passed:
        return "High", (
            f"Single authoritative in-effect policy ({next(iter(policy_ids))}) "
            f"found with similarity {top_score:.3f}, all docs DQ-passed."
        )
    if top_score >= 0.65 and all_passed:
        return "Medium", (
            f"Relevant policy found (similarity {top_score:.3f}) "
            f"but {'multiple policies' if not single_authoritative else 'supporting docs have DQ warnings'}."
        )
    return "Low", (
        f"Low retrieval confidence (top similarity {top_score:.3f}) "
        "or DQ issues in supporting documents."
    )
