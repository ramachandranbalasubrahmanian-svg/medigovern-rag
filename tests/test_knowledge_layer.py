"""Tests for knowledge layer: chunking, indexing, and ingest-and-index pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.database import SessionLocal, init_db
from app.models.metadata import (
    DQStatus,
    DocumentMetadata,
    DocumentType,
    Sensitivity,
    SourceSystem,
)
from pipeline.embeddings.chunker import chunk_document
from pipeline.embeddings.pipeline import _indexable_documents, ingest_and_index
from pipeline.ingestion.base import IngestedDocument


def _policy_doc(
    *,
    dq_status: DQStatus = DQStatus.PASSED,
    raw_content: str | None = None,
) -> IngestedDocument:
    if raw_content is None:
        content = (
            "SYNTHETIC PAYER MEDICAL POLICY\n"
            "Payer: AcmeHealth\n"
            "Plan ID: GOLD-PPO\n"
            "Policy ID: POL-TEST\n"
            "Title: Test MRI Policy\n"
            "Procedure Codes: 70553\n"
            "PA Required: YES\n\n"
            "PRIOR AUTHORIZATION REQUIREMENTS\n"
            "Authorization required for neurological indications. "
            "Documented failed conservative therapy is required before approval.\n\n"
            "REGULATORY NOTE\n"
            "CMS-0057-F compliance demonstration data. "
            "All data is synthetic and not for clinical use."
        )
    else:
        content = raw_content
    meta = DocumentMetadata(
        source_system=SourceSystem.POLICY_PDF,
        document_type=DocumentType.MEDICAL_POLICY,
        title="Test Policy",
        policy_id="POL-TEST",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        effective_date=date(2025, 1, 1),
        procedure_codes=["70553"],
        data_owner="test",
        source_uri="data/raw/policies/test.pdf",
        sensitivity=Sensitivity.SYNTHETIC,
        dq_status=dq_status,
    )
    return IngestedDocument(metadata=meta, raw_content=content)


class TestChunker:
    def test_policy_splits_on_section_headers(self):
        doc = _policy_doc()
        chunks = chunk_document(doc)
        assert len(chunks) >= 2
        labels = {c.section_label for c in chunks if c.section_label}
        assert "PRIOR AUTHORIZATION REQUIREMENTS" in labels
        assert "REGULATORY NOTE" in labels

    def test_chunks_carry_lineage_and_metadata(self):
        doc = _policy_doc()
        chunks = chunk_document(doc)
        chunk = chunks[0]
        assert chunk.document_id == doc.metadata.document_id
        assert chunk.source_uri == doc.metadata.source_uri
        assert chunk.payer == "AcmeHealth"
        assert chunk.plan_id == "GOLD-PPO"
        assert "70553" in chunk.procedure_codes
        assert chunk.dq_status == DQStatus.PASSED

    def test_empty_content_returns_no_chunks(self):
        doc = _policy_doc(raw_content="")
        assert chunk_document(doc) == []

    def test_non_policy_splits_paragraphs(self):
        meta = DocumentMetadata(
            source_system=SourceSystem.FHIR,
            document_type=DocumentType.PATIENT_BUNDLE,
            title="Bundle",
            payer="AcmeHealth",
            plan_id="GOLD-PPO",
            effective_date=None,
            data_owner="test",
            source_uri="data/raw/fhir/bundle.json",
            sensitivity=Sensitivity.SYNTHETIC,
        )
        long_para = "Clinical context paragraph. " * 40  # ~1000 chars each
        doc = IngestedDocument(
            metadata=meta,
            raw_content=f"{long_para}\n\n{long_para}\n\n{long_para}",
        )
        chunks = chunk_document(doc)
        assert len(chunks) >= 2


class TestIndexableDocuments:
    def test_quarantined_excluded(self):
        passed = _policy_doc(dq_status=DQStatus.PASSED)
        warned = _policy_doc(dq_status=DQStatus.WARNING)
        quarantined = _policy_doc(dq_status=DQStatus.QUARANTINED)
        result = _indexable_documents([passed, warned, quarantined])
        ids = {d.metadata.document_id for d in result}
        assert passed.metadata.document_id in ids
        assert warned.metadata.document_id in ids
        assert quarantined.metadata.document_id not in ids

    def test_empty_content_excluded(self):
        doc = _policy_doc(raw_content="   ")
        assert _indexable_documents([doc]) == []


@pytest.fixture(scope="module")
def postgres_available() -> bool:
    try:
        init_db()
        session = SessionLocal()
        session.connection()
        session.close()
        return True
    except Exception:
        return False


class TestIngestAndIndexIntegration:
    RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def ensure_data(cls):
        if not (cls.RAW_DIR / "policies").exists():
            from scripts.generate_synthetic_data import generate_all

            generate_all(verbose=False)

    def test_full_index_build(self, postgres_available):
        if not postgres_available:
            pytest.skip("Postgres not available")

        report = ingest_and_index(raw_dir=self.RAW_DIR, reindex=True)

        assert report.docs_ingested == 35
        assert report.docs_quarantined == 4
        assert report.docs_indexed == report.docs_passed + report.docs_warning
        assert report.chunks_embedded > 0
        assert report.chunks_embedded >= report.docs_indexed

        # Quarantined docs must not be embedded
        from app.db.models import DocumentChunkRecord, DocumentMetadataRecord
        from sqlalchemy import select

        session = SessionLocal()
        try:
            quarantined_ids = {
                row.document_id
                for row in session.scalars(
                    select(DocumentMetadataRecord).where(
                        DocumentMetadataRecord.dq_status == DQStatus.QUARANTINED
                    )
                )
            }
            chunk_doc_ids = {
                row.document_id
                for row in session.scalars(select(DocumentChunkRecord.document_id))
            }
            assert quarantined_ids.isdisjoint(chunk_doc_ids)
        finally:
            session.close()
