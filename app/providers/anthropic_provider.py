"""Anthropic LLM provider."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import LLMProvider


class AnthropicLLMProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
            )
        self._api_key = settings.anthropic_api_key
        self._model = settings.anthropic_model

    def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": kwargs.pop("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        if system:
            payload["system"] = system

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        content = response.json()["content"]
        return content[0]["text"]
