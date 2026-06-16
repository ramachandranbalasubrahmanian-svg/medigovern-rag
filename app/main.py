"""MediGovern RAG FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.ask import router as ask_router
from app.api.audit import router as audit_router
from app.config import get_settings
from app.database import get_db, init_db
from app.providers import get_embeddings_provider, get_llm_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="MediGovern RAG",
    description=(
        "Healthcare prior-authorization data-governance RAG pipeline.\n\n"
        "FHIR-aware ingestion · metadata-driven retrieval · DQ gating · auditable citations.\n\n"
        "**All data is synthetic — for demonstration purposes only.**"
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(ask_router, tags=["Q&A"])
app.include_router(audit_router, tags=["Audit"])


@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "medigovern-rag", "version": "0.2.0"}


@app.get("/", tags=["System"])
def root() -> dict:
    settings = get_settings()
    return {
        "service": "MediGovern RAG",
        "version": "0.2.0",
        "llm_provider": settings.llm_provider,
        "embeddings_provider": settings.embeddings_provider,
    }


@app.get("/providers/status", tags=["System"])
def providers_status() -> dict:
    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "embeddings_provider": settings.embeddings_provider,
        "openai_configured": bool(settings.openai_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "llm_class": type(get_llm_provider()).__name__,
        "embeddings_class": type(get_embeddings_provider()).__name__,
    }
