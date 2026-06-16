"""MediGovern RAG FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, init_db
from app.providers import get_embeddings_provider, get_llm_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="MediGovern RAG",
    description="Healthcare prior-authorization data-governance RAG pipeline",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "medigovern-rag"}


@app.get("/")
def root() -> dict:
    settings = get_settings()
    return {
        "service": "MediGovern RAG",
        "version": "0.1.0",
        "llm_provider": settings.llm_provider,
        "embeddings_provider": settings.embeddings_provider,
    }


@app.get("/providers/status")
def providers_status() -> dict:
    """Report which provider backends are configured (no API calls)."""
    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "embeddings_provider": settings.embeddings_provider,
        "openai_configured": bool(settings.openai_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "llm_class": type(get_llm_provider()).__name__,
        "embeddings_class": type(get_embeddings_provider()).__name__,
    }
