"""MediGovern RAG FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.ask import router as ask_router
from app.api.audit import router as audit_router
from app.api.catalog import router as catalog_router
from app.config import get_settings
from app.database import SessionLocal, get_db, init_db
from app.providers import get_embeddings_provider, get_llm_provider

logger = logging.getLogger("medigovern")


def _seed_if_empty() -> None:
    """Run the full ingest-and-index pipeline if the knowledge base is empty."""
    settings = get_settings()
    if not settings.seed_on_startup:
        return

    try:
        from app.db.models import DocumentChunkRecord

        db = SessionLocal()
        try:
            count = db.scalar(select(func.count()).select_from(DocumentChunkRecord))
        finally:
            db.close()

        if count and count > 0:
            logger.info("Knowledge base already seeded (%d chunks). Skipping.", count)
            return

        logger.info("Knowledge base empty — running ingest-and-index...")
        from pipeline.embeddings.pipeline import ingest_and_index

        report = ingest_and_index()
        logger.info(
            "Seeding complete: %d docs indexed, %d chunks embedded.",
            report.docs_indexed,
            report.chunks_embedded,
        )
    except Exception as exc:
        logger.warning("Seeding skipped (DB not available or error): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_if_empty()
    yield


settings = get_settings()

app = FastAPI(
    title="MediGovern RAG",
    description=(
        "Healthcare prior-authorization data-governance RAG pipeline.\n\n"
        "FHIR-aware ingestion · metadata-driven retrieval · DQ gating · auditable citations.\n\n"
        "**All data is synthetic — for demonstration purposes only.**"
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# CORS — allow configured origins (defaults include localhost:3000/5173 and lovable.app)
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.lovable\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask_router, tags=["Q&A"])
app.include_router(audit_router, tags=["Audit"])
app.include_router(catalog_router)


@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "medigovern-rag", "version": "0.3.0"}


@app.get("/", tags=["System"])
def root() -> dict:
    s = get_settings()
    return {
        "service": "MediGovern RAG",
        "version": "0.3.0",
        "llm_provider": s.llm_provider,
        "embeddings_provider": s.embeddings_provider,
        "docs": "/docs",
    }


@app.get("/providers/status", tags=["System"])
def providers_status() -> dict:
    s = get_settings()
    return {
        "llm_provider": s.llm_provider,
        "embeddings_provider": s.embeddings_provider,
        "openai_configured": bool(s.openai_api_key),
        "anthropic_configured": bool(s.anthropic_api_key),
        "llm_class": type(get_llm_provider()).__name__,
        "embeddings_class": type(get_embeddings_provider()).__name__,
    }
