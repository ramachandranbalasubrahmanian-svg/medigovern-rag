"""Persist document metadata and vector chunks to Postgres."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import DocumentChunkRecord, DocumentMetadataRecord
from app.models.chunk import DocumentChunk
from pipeline.ingestion.base import IngestedDocument


def clear_index(session: Session) -> None:
    """Remove all chunks and metadata (full re-index)."""
    session.execute(delete(DocumentChunkRecord))
    session.execute(delete(DocumentMetadataRecord))
    session.commit()


def upsert_documents(session: Session, documents: list[IngestedDocument]) -> int:
    """Persist all ingested documents to document_metadata."""
    count = 0
    for doc in documents:
        meta = doc.metadata
        record = DocumentMetadataRecord(
            document_id=meta.document_id,
            source_system=meta.source_system,
            document_type=meta.document_type,
            title=meta.title,
            policy_id=meta.policy_id,
            payer=meta.payer,
            plan_id=meta.plan_id,
            effective_date=meta.effective_date,
            expiry_date=meta.expiry_date,
            procedure_codes=list(meta.procedure_codes),
            diagnosis_codes=list(meta.diagnosis_codes),
            data_owner=meta.data_owner,
            steward=meta.steward,
            source_uri=meta.source_uri,
            ingested_at=meta.ingested_at,
            version=meta.version,
            sensitivity=meta.sensitivity,
            dq_status=meta.dq_status,
            dq_findings=[f.model_dump() for f in meta.dq_findings],
        )
        session.merge(record)
        count += 1
    session.commit()
    return count


def store_chunks(
    session: Session,
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
) -> int:
    """Store chunks with their embedding vectors."""
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunk/embedding count mismatch: {len(chunks)} vs {len(embeddings)}"
        )

    now = datetime.now(timezone.utc)
    for chunk, vector in zip(chunks, embeddings):
        record = DocumentChunkRecord(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            source_uri=chunk.source_uri,
            chunk_index=chunk.chunk_index,
            chunk_text=chunk.chunk_text,
            section_label=chunk.section_label,
            policy_id=chunk.policy_id,
            payer=chunk.payer,
            plan_id=chunk.plan_id,
            effective_date=chunk.effective_date,
            expiry_date=chunk.expiry_date,
            procedure_codes=list(chunk.procedure_codes),
            diagnosis_codes=list(chunk.diagnosis_codes),
            dq_status=chunk.dq_status,
            document_type=chunk.document_type,
            source_system=chunk.source_system,
            embedding=vector,
            embedded_at=now,
        )
        session.merge(record)
    session.commit()
    return len(chunks)
