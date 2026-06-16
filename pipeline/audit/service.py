"""Orchestrates retrieval → generation → audit packet building."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from pipeline.audit.log import append_audit_log, render_html
from pipeline.audit.models import AuditChunkCitation, AuditPacket
from pipeline.retrieval.generator import generate_answer
from pipeline.retrieval.retriever import retrieve


def ask(
    session: Session,
    question: str,
    *,
    plan_id: str | None = None,
    payer: str | None = None,
    cpt: str | None = None,
    user_role: str = "anonymous",
) -> tuple[AuditPacket, str]:
    """Full RAG pipeline: retrieve → generate → audit. Returns (packet, html)."""
    settings = get_settings()

    retrieval = retrieve(session, question, plan_id=plan_id, payer=payer, cpt=cpt)
    generation = generate_answer(retrieval)

    all_chunks_as_citations = [
        AuditChunkCitation(
            policy_id=c.policy_id,
            section_label=c.section_label,
            source_uri=c.source_uri,
            effective_date=str(c.effective_date) if c.effective_date else None,
            expiry_date=str(c.expiry_date) if c.expiry_date else None,
            dq_status=c.dq_status,
            chunk_text_snippet=c.chunk_text[:200],
        )
        for c in retrieval.chunks
    ]

    gen_citations = [
        AuditChunkCitation(
            policy_id=cit.policy_id,
            section_label=cit.section_label,
            source_uri=cit.source_uri,
            effective_date=cit.effective_date,
            expiry_date=cit.expiry_date,
            dq_status=cit.dq_status,
            chunk_text_snippet=cit.chunk_text_snippet,
        )
        for cit in generation.citations
    ]

    packet = AuditPacket(
        question=question,
        user_role=user_role,
        plan_id=plan_id,
        payer=payer,
        cpt=cpt,
        filters_applied=retrieval.filters_applied,
        retrieved_chunks=all_chunks_as_citations,
        model_provider=settings.llm_provider,
        model_name=_model_name(settings),
        answer=generation.answer,
        confidence=generation.confidence,
        confidence_rationale=generation.confidence_rationale,
        citations=gen_citations,
        missing_data=generation.missing_data,
        abstained=generation.abstained,
        abstain_reason=generation.abstain_reason,
    )

    append_audit_log(session, packet)
    audit_html = render_html(packet)

    return packet, audit_html


def _model_name(settings) -> str:
    p = settings.llm_provider
    if p == "openai":
        return settings.openai_model
    if p == "anthropic":
        return settings.anthropic_model
    return "local_stub"
