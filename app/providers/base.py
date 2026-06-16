"""Abstract provider interfaces and factory functions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.config import ProviderName, get_settings


class LLMProvider(ABC):
    """Interface for text generation backends."""

    @abstractmethod
    def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        """Generate a completion for the given prompt."""


class EmbeddingsProvider(ABC):
    """Interface for embedding backends."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for each input text."""


class LocalLLMProvider(LLMProvider):
    """Stub local provider for development without API keys."""

    def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        return "[local stub] LLM response not configured."


class LocalEmbeddingsProvider(EmbeddingsProvider):
    """Deterministic stub embeddings for local development."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text) % 10) / 10.0] * 8 for text in texts]


def get_llm_provider(name: ProviderName | None = None) -> LLMProvider:
    settings = get_settings()
    provider = name or settings.llm_provider

    if provider == "openai":
        if not settings.openai_api_key:
            return LocalLLMProvider()
        from app.providers.openai_provider import OpenAILLMProvider

        return OpenAILLMProvider()
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return LocalLLMProvider()
        from app.providers.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider()
    return LocalLLMProvider()


def get_embeddings_provider(name: ProviderName | None = None) -> EmbeddingsProvider:
    settings = get_settings()
    provider = name or settings.embeddings_provider

    if provider == "openai":
        if not settings.openai_api_key:
            return LocalEmbeddingsProvider()
        from app.providers.openai_provider import OpenAIEmbeddingsProvider

        return OpenAIEmbeddingsProvider()
    if provider == "sentence-transformers":
        from app.providers.fastembed_provider import FastEmbedEmbeddingsProvider

        return FastEmbedEmbeddingsProvider()
    return LocalEmbeddingsProvider()
