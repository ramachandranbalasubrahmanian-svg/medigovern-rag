"""Sentence-transformers embeddings provider via fastembed (no API key required).

Uses ONNX runtime — CPU-friendly, ~30 MB model, zero external API calls.
Model: BAAI/bge-small-en-v1.5  →  384-dimensional vectors.
"""

from __future__ import annotations

from app.providers.base import EmbeddingsProvider

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSION = 384


class FastEmbedEmbeddingsProvider(EmbeddingsProvider):
    """Local embeddings using fastembed (ONNX, CPU-friendly, no API key)."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding  # deferred import — avoid load at config time

        self._model = TextEmbedding(model_name=_MODEL_NAME)

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = list(self._model.embed(texts))
        return [e.tolist() for e in embeddings]
