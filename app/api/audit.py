"""GET /audit/{id} — retrieve a full audit packet."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from pipeline.audit.log import get_audit_record, render_html
from pipeline.audit.models import AuditPacket

router = APIRouter()


@router.get(
    "/audit/{audit_id}",
    summary="Fetch a full audit packet by ID",
    responses={
        200: {"description": "Audit packet JSON"},
        404: {"description": "Not found"},
    },
)
def get_audit(audit_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    """Return the full JSON audit packet for a prior query."""
    record = get_audit_record(db, audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Audit packet {audit_id} not found")
    return JSONResponse(content=record.packet_json)


@router.get(
    "/audit/{audit_id}/html",
    response_class=HTMLResponse,
    summary="Fetch a rendered HTML audit packet",
)
def get_audit_html(audit_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """Return a styled HTML audit report for a prior query."""
    record = get_audit_record(db, audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Audit packet {audit_id} not found")
    packet = AuditPacket.model_validate(record.packet_json)
    return HTMLResponse(content=render_html(packet))
