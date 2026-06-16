"""Application configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ProviderName = Literal["openai", "anthropic", "sentence-transformers", "local"]


class Settings(BaseSettings):
    """Central configuration loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql://medigovern:medigovern@localhost:5432/medigovern",
        alias="DATABASE_URL",
    )

    llm_provider: ProviderName = Field(default="anthropic", alias="LLM_PROVIDER")
    embeddings_provider: ProviderName = Field(
        default="sentence-transformers", alias="EMBEDDINGS_PROVIDER"
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514", alias="ANTHROPIC_MODEL"
    )

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Vector dimension — auto 8 (local) or 1536 (openai) when unset
    embedding_dimension: int | None = Field(default=None, alias="EMBEDDING_DIMENSION")
    chunk_max_chars: int = Field(default=1200, alias="CHUNK_MAX_CHARS")

    # CORS — comma-separated allowed origins for the front-end
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,https://*.lovable.app",
        alias="CORS_ORIGINS",
    )

    # Seed the knowledge base on startup if empty (set to "false" to disable)
    seed_on_startup: bool = Field(default=True, alias="SEED_ON_STARTUP")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_embedding_dimension(settings: Settings | None = None) -> int:
    """Resolved embedding vector size for pgvector column."""
    s = settings or get_settings()
    if s.embedding_dimension is not None:
        return s.embedding_dimension
    if s.embeddings_provider == "openai":
        return 1536
    if s.embeddings_provider == "sentence-transformers":
        return 384
    return 8
