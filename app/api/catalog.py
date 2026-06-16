"""Dashboard catalog endpoints: policies, quarantine, audit history."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.models import DocumentMetadataRecord
from app.models.metadata import DQStatus
from pipeline.audit.log import AuditLogRecord

router = APIRouter(tags=["Dashboard"])


# ---------------------------------------------------------------------------
# GET /policies
# ---------------------------------------------------------------------------

class PolicyOut(dict):
    pass


@router.get("/policies", summary="Policy catalog with metadata and lineage")
def list_policies(
    payer: str | None = Query(None),
    plan_id: str | None = Query(None),
    cpt: str | None = Query(None),
    dq_status: str | None = Query(None, description="passed | warning | quarantined"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Searchable policy catalog.  Filter by payer, plan, CPT code, or DQ status.
    Returns metadata + source lineage for every matching document.
    """
    q = select(DocumentMetadataRecord)

    if payer:
        q = q.where(DocumentMetadataRecord.payer == payer)
    if plan_id:
        q = q.where(DocumentMetadataRecord.plan_id == plan_id)
    if cpt:
        q = q.where(DocumentMetadataRecord.procedure_codes.contains([cpt]))
    if dq_status:
        q = q.where(DocumentMetadataRecord.dq_status == DQStatus(dq_status))

    q = q.order_by(DocumentMetadataRecord.ingested_at.desc()).offset(offset).limit(limit)
    rows = db.scalars(q).all()

    return [_policy_row(r) for r in rows]


@router.get("/policies/{document_id}", summary="Single policy detail")
def get_policy(document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from sqlalchemy.exc import NoResultFound
    import uuid
    from fastapi import HTTPException

    try:
        uid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    record = db.get(DocumentMetadataRecord, uid)
    if record is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _policy_row(record)


def _policy_row(r: DocumentMetadataRecord) -> dict[str, Any]:
    return {
        "document_id": str(r.document_id),
        "title": r.title,
        "policy_id": r.policy_id,
        "document_type": r.document_type.value if hasattr(r.document_type, "value") else str(r.document_type),
        "source_system": r.source_system.value if hasattr(r.source_system, "value") else str(r.source_system),
        "payer": r.payer,
        "plan_id": r.plan_id,
        "effective_date": str(r.effective_date) if r.effective_date else None,
        "expiry_date": str(r.expiry_date) if r.expiry_date else None,
        "procedure_codes": list(r.procedure_codes or []),
        "diagnosis_codes": list(r.diagnosis_codes or []),
        "data_owner": r.data_owner,
        "source_uri": r.source_uri,
        "dq_status": r.dq_status.value if hasattr(r.dq_status, "value") else str(r.dq_status),
        "dq_findings": list(r.dq_findings or []),
        "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
        "version": r.version,
        "sensitivity": r.sensitivity.value if hasattr(r.sensitivity, "value") else str(r.sensitivity),
    }


# ---------------------------------------------------------------------------
# GET /quarantine
# ---------------------------------------------------------------------------

@router.get("/quarantine", summary="Quarantined records with DQ findings")
def list_quarantine(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    All documents in quarantine status.  Shows the DQ rule findings that
    caused them to be excluded from retrieval.
    """
    q = (
        select(DocumentMetadataRecord)
        .where(DocumentMetadataRecord.dq_status == DQStatus.QUARANTINED)
        .order_by(DocumentMetadataRecord.ingested_at.desc())
        .limit(limit)
    )
    rows = db.scalars(q).all()
    return [_policy_row(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /audit (history)
# ---------------------------------------------------------------------------

@router.get("/audit", summary="Recent query history (audit log)")
def list_audit_history(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Recent Q&A history from the append-only audit log.
    Each entry links to the full audit packet via GET /audit/{id}.
    """
    q = (
        select(AuditLogRecord)
        .order_by(desc(AuditLogRecord.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(q).all()
    return [
        {
            "audit_id": str(r.audit_id),
            "created_at": r.created_at.isoformat(),
            "question": r.question,
            "plan_id": r.plan_id,
            "payer": r.payer,
            "cpt": r.cpt,
            "confidence": r.confidence,
            "abstained": r.abstained,
            "model_provider": r.model_provider,
            "model_name": r.model_name,
        }
        for r in rows
    ]
