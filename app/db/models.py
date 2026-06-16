"""SQLAlchemy tables for document metadata and vector chunks."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_embedding_dimension
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

    chunks: Mapped[list["DocumentChunkRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DocumentMetadataRecord {self.document_id} {self.title!r}>"


class DocumentChunkRecord(Base):
    """Vector chunk with structured metadata index and lineage pointers."""

    __tablename__ = "document_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_metadata.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_label: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Structured metadata index for pre-filtered retrieval
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payer: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    procedure_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    diagnosis_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    dq_status: Mapped[DQStatus] = mapped_column(
        Enum(DQStatus, name="chunk_dq_status_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="chunk_document_type_enum", native_enum=False),
        nullable=False,
    )
    source_system: Mapped[SourceSystem] = mapped_column(
        Enum(SourceSystem, name="chunk_source_system_enum", native_enum=False),
        nullable=False,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_embedding_dimension()), nullable=True
    )
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    document: Mapped[DocumentMetadataRecord] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunkRecord {self.chunk_id} doc={self.document_id} idx={self.chunk_index}>"
