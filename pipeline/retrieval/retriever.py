"""Metadata-filtered semantic retrieval from pgvector.

Design (plan section 5.5):
  1. Pre-filter on structured metadata (plan_id, payer, CPT, date window, dq_status=passed)
  2. Semantic search (cosine distance) within the filtered set
  3. Return ranked chunks + detect conflicts in the result set
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import and_, cast, func, or_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session
from sqlalchemy.types import String

from app.db.models import DocumentChunkRecord
from app.models.metadata import DQStatus
from app.providers import get_embeddings_provider


TOP_K = 8  # candidates returned before re-ranking


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    source_uri: str
    chunk_index: int
    chunk_text: str
    section_label: str | None
    policy_id: str | None
    payer: str | None
    plan_id: str | None
    effective_date: date | None
    expiry_date: date | None
    procedure_codes: list[str]
    diagnosis_codes: list[str]
    dq_status: str
    document_type: str
    similarity_score: float


@dataclass
class RetrievalResult:
    query: str
    filters_applied: dict
    chunks: list[RetrievedChunk] = field(default_factory=list)
    has_conflict: bool = False
    conflict_detail: str = ""
    no_policy_found: bool = False


def retrieve(
    session: Session,
    question: str,
    *,
    plan_id: str | None = None,
    payer: str | None = None,
    cpt: str | None = None,
    top_k: int = TOP_K,
) -> RetrievalResult:
    """Pre-filter metadata, then semantic search.  Returns ranked chunks + conflict flag."""
    filters_applied = {
        "plan_id": plan_id,
        "payer": payer,
        "cpt": cpt,
        "dq_status": "passed",
        "date_window": "effective_date<=today<=expiry_date",
    }

    query_vector = get_embeddings_provider().embed([question])[0]
    today = date.today()

    conditions = [
        DocumentChunkRecord.dq_status == DQStatus.PASSED,
        DocumentChunkRecord.embedding.is_not(None),
        # Date window: effective_date is before or on today
        or_(
            DocumentChunkRecord.effective_date.is_(None),
            DocumentChunkRecord.effective_date <= today,
        ),
        # expiry_date is null (no expiry) or in the future
        or_(
            DocumentChunkRecord.expiry_date.is_(None),
            DocumentChunkRecord.expiry_date >= today,
        ),
    ]

    if plan_id:
        conditions.append(DocumentChunkRecord.plan_id == plan_id)
    if payer:
        conditions.append(DocumentChunkRecord.payer == payer)
    if cpt:
        conditions.append(
            DocumentChunkRecord.procedure_codes.contains(
                cast([cpt], ARRAY(String))
            )
        )

    rows = (
        session.query(
            DocumentChunkRecord,
            (1 - DocumentChunkRecord.embedding.cosine_distance(query_vector)).label(
                "similarity"
            ),
        )
        .filter(and_(*conditions))
        .order_by(
            DocumentChunkRecord.embedding.cosine_distance(query_vector)
        )
        .limit(top_k)
        .all()
    )

    chunks = [
        RetrievedChunk(
            chunk_id=str(row.DocumentChunkRecord.chunk_id),
            document_id=str(row.DocumentChunkRecord.document_id),
            source_uri=row.DocumentChunkRecord.source_uri,
            chunk_index=row.DocumentChunkRecord.chunk_index,
            chunk_text=row.DocumentChunkRecord.chunk_text,
            section_label=row.DocumentChunkRecord.section_label,
            policy_id=row.DocumentChunkRecord.policy_id,
            payer=row.DocumentChunkRecord.payer,
            plan_id=row.DocumentChunkRecord.plan_id,
            effective_date=row.DocumentChunkRecord.effective_date,
            expiry_date=row.DocumentChunkRecord.expiry_date,
            procedure_codes=list(row.DocumentChunkRecord.procedure_codes or []),
            diagnosis_codes=list(row.DocumentChunkRecord.diagnosis_codes or []),
            dq_status=row.DocumentChunkRecord.dq_status.value
            if hasattr(row.DocumentChunkRecord.dq_status, "value")
            else str(row.DocumentChunkRecord.dq_status),
            document_type=row.DocumentChunkRecord.document_type.value
            if hasattr(row.DocumentChunkRecord.document_type, "value")
            else str(row.DocumentChunkRecord.document_type),
            similarity_score=float(row.similarity),
        )
        for row in rows
    ]

    result = RetrievalResult(query=question, filters_applied=filters_applied, chunks=chunks)

    if not chunks:
        result.no_policy_found = True
        return result

    # Conflict detection: active policies with opposite PA requirements in same scope
    result.has_conflict, result.conflict_detail = _detect_conflict(chunks)
    return result


def _detect_conflict(chunks: list[RetrievedChunk]) -> tuple[bool, str]:
    """Return (True, reason) if retrieved chunks show conflicting PA requirements."""
    pa_by_policy: dict[str, str] = {}
    for chunk in chunks:
        if not chunk.policy_id:
            continue
        text_upper = chunk.chunk_text.upper()
        if "PA REQUIRED: YES" in text_upper or "PRIOR AUTHORIZATION REQUIRED" in text_upper:
            pa_by_policy[chunk.policy_id] = "YES"
        elif "PA REQUIRED: NO" in text_upper or "NO PRIOR AUTHORIZATION" in text_upper:
            pa_by_policy[chunk.policy_id] = "NO"

    yes_policies = [p for p, v in pa_by_policy.items() if v == "YES"]
    no_policies = [p for p, v in pa_by_policy.items() if v == "NO"]

    if yes_policies and no_policies:
        detail = (
            f"Active policies with conflicting PA requirements: "
            f"PA=YES ({', '.join(yes_policies)}) vs PA=NO ({', '.join(no_policies)})"
        )
        return True, detail

    return False, ""
