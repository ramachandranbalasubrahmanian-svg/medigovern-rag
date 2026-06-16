"""POST /ask — prior-authorization Q&A endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from pipeline.audit.service import ask as ask_service

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    plan_id: str | None = None
    payer: str | None = None
    cpt: str | None = None
    user_role: str = "anonymous"


class CitationOut(BaseModel):
    policy_id: str | None
    section_label: str | None
    source_uri: str
    effective_date: str | None
    expiry_date: str | None
    dq_status: str
    chunk_text_snippet: str


class AskResponse(BaseModel):
    audit_packet_id: str
    answer: str
    confidence: str
    confidence_rationale: str
    citations: list[CitationOut]
    missing_data: list[str]
    abstained: bool
    abstain_reason: str


@router.post("/ask", response_model=AskResponse, summary="Ask a prior-authorization question")
def ask_endpoint(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    """
    Submit a plain-English prior-authorization question.

    Optionally scope by **plan_id**, **payer**, or **cpt** (CPT code).

    Returns a cited answer, confidence band, missing data findings, and an
    audit packet ID for full lineage retrieval via GET /audit/{id}.
    """
    try:
        packet, _html = ask_service(
            db,
            request.question,
            plan_id=request.plan_id,
            payer=request.payer,
            cpt=request.cpt,
            user_role=request.user_role,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AskResponse(
        audit_packet_id=str(packet.audit_id),
        answer=packet.answer,
        confidence=packet.confidence,
        confidence_rationale=packet.confidence_rationale,
        citations=[
            CitationOut(
                policy_id=c.policy_id,
                section_label=c.section_label,
                source_uri=c.source_uri,
                effective_date=c.effective_date,
                expiry_date=c.expiry_date,
                dq_status=c.dq_status,
                chunk_text_snippet=c.chunk_text_snippet,
            )
            for c in packet.citations
        ],
        missing_data=packet.missing_data,
        abstained=packet.abstained,
        abstain_reason=packet.abstain_reason,
    )
