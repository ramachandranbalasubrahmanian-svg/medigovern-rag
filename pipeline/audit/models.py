"""Pydantic models for audit packets and audit log entries."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AuditChunkCitation(BaseModel):
    policy_id: str | None
    section_label: str | None
    source_uri: str
    effective_date: str | None
    expiry_date: str | None
    dq_status: str
    chunk_text_snippet: str


class AuditPacket(BaseModel):
    """Complete, immutable record of one answered question."""

    audit_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Request
    question: str
    user_role: str = "anonymous"
    plan_id: str | None = None
    payer: str | None = None
    cpt: str | None = None

    # Retrieval
    filters_applied: dict = Field(default_factory=dict)
    retrieved_chunks: list[AuditChunkCitation] = Field(default_factory=list)

    # Generation
    model_provider: str = "local"
    model_name: str = "local_stub"
    answer: str
    confidence: str
    confidence_rationale: str
    citations: list[AuditChunkCitation] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    abstained: bool = False
    abstain_reason: str = ""

    model_config = {"from_attributes": True}
