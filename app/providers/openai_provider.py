"""OpenAI LLM and embeddings provider."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import EmbeddingsProvider, LLMProvider


class OpenAILLMProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self._api_key = settings.openai_api_key
        self._model = settings.openai_model

    def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages, **kwargs},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class OpenAIEmbeddingsProvider(EmbeddingsProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when EMBEDDINGS_PROVIDER=openai"
            )
        self._api_key = settings.openai_api_key
        self._model = settings.openai_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "input": texts},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
