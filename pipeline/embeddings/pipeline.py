"""Knowledge layer pipeline: ingest -> DQ -> chunk -> embed -> store."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models.metadata import DQStatus
from pipeline.dq.report import DQReport
from pipeline.embeddings.chunker import chunk_documents
from pipeline.embeddings.indexer import embed_and_store
from pipeline.embeddings.store import clear_index, upsert_documents
from pipeline.ingestion.base import IngestedDocument
from pipeline.ingestion.pipeline import RAW_DIR, run as run_ingestion


@dataclass
class IndexReport:
    """Summary of a full ingest-and-index run."""

    docs_ingested: int = 0
    docs_passed: int = 0
    docs_warning: int = 0
    docs_quarantined: int = 0
    docs_indexed: int = 0
    chunks_embedded: int = 0
    dq_report: DQReport | None = None
    errors: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("  MediGovern RAG — Ingest & Index Report")
        print("=" * 60)
        print(f"  Docs ingested    : {self.docs_ingested}")
        print(f"  Passed           : {self.docs_passed}")
        print(f"  Warning          : {self.docs_warning}")
        print(f"  Quarantined      : {self.docs_quarantined}")
        print(f"  Docs indexed     : {self.docs_indexed}  (non-quarantined only)")
        print(f"  Chunks embedded  : {self.chunks_embedded}")
        if self.errors:
            print(f"  Errors           : {len(self.errors)}")
        print("=" * 60 + "\n")


def ingest_and_index(
    raw_dir: Path = RAW_DIR,
    session: Session | None = None,
    *,
    reindex: bool = True,
) -> IndexReport:
    """Full path: load -> extract -> DQ gate -> chunk -> embed -> store."""
    init_db()

    documents, dq_report = run_ingestion(raw_dir=raw_dir)
    report = IndexReport(
        docs_ingested=len(documents),
        docs_passed=sum(1 for d in documents if d.metadata.dq_status == DQStatus.PASSED),
        docs_warning=sum(1 for d in documents if d.metadata.dq_status == DQStatus.WARNING),
        docs_quarantined=sum(
            1 for d in documents if d.metadata.dq_status == DQStatus.QUARANTINED
        ),
        dq_report=dq_report,
        errors=list(dq_report.errors),
    )

    own_session = session is None
    db = session or SessionLocal()
    try:
        if reindex:
            clear_index(db)

        upsert_documents(db, documents)

        indexable = _indexable_documents(documents)
        report.docs_indexed = len(indexable)

        chunks = chunk_documents(indexable)
        report.chunks_embedded = embed_and_store(db, chunks)
    finally:
        if own_session:
            db.close()

    return report


def _indexable_documents(documents: list[IngestedDocument]) -> list[IngestedDocument]:
    """Return documents eligible for embedding (passed + warning, not quarantined)."""
    return [
        d
        for d in documents
        if d.metadata.dq_status != DQStatus.QUARANTINED and (d.raw_content or "").strip()
    ]
