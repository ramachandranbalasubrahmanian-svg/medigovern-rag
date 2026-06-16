"""SQLAlchemy table for canonical document metadata (section 5.2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.metadata import (
    DQStatus,
    DocumentType,
    Sensitivity,
    SourceSystem,
)


class DocumentMetadataRecord(Base):
    """Persistent metadata record for ingested artifacts."""

    __tablename__ = "document_metadata"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_system: Mapped[SourceSystem] = mapped_column(
        Enum(SourceSystem, name="source_system_enum", native_enum=False)
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum", native_enum=False)
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    procedure_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    diagnosis_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    data_owner: Mapped[str | None] = mapped_column(String(256), nullable=True)
    steward: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sensitivity: Mapped[Sensitivity] = mapped_column(
        Enum(Sensitivity, name="sensitivity_enum", native_enum=False),
        nullable=False,
        default=Sensitivity.SYNTHETIC,
    )
    dq_status: Mapped[DQStatus] = mapped_column(
        Enum(DQStatus, name="dq_status_enum", native_enum=False),
        nullable=False,
        default=DQStatus.PASSED,
    )
    dq_findings: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    def __repr__(self) -> str:
        return f"<DocumentMetadataRecord {self.document_id} {self.title!r}>"
