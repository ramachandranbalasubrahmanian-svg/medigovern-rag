"""Pydantic models for document chunks."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.metadata import DQStatus, DocumentType, SourceSystem


class DocumentChunk(BaseModel):
    """A text chunk with lineage and denormalized metadata for pre-filtering."""

    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    source_uri: str
    chunk_index: int
    chunk_text: str
    section_label: str | None = None

    # Structured metadata index (denormalized from parent document)
    policy_id: str | None = None
    payer: str | None = None
    plan_id: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    procedure_codes: list[str] = Field(default_factory=list)
    diagnosis_codes: list[str] = Field(default_factory=list)
    dq_status: DQStatus
    document_type: DocumentType
    source_system: SourceSystem

    embedded_at: datetime | None = None

    model_config = {"from_attributes": True}
