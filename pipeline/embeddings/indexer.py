"""Generate embeddings and persist chunks to pgvector."""

from __future__ import annotations

from app.providers import get_embeddings_provider
from app.models.chunk import DocumentChunk
from pipeline.embeddings.store import store_chunks
from sqlalchemy.orm import Session

BATCH_SIZE = 32


def embed_and_store(
    session: Session,
    chunks: list[DocumentChunk],
) -> int:
    """Embed all chunks via the configured provider and store in pgvector."""
    if not chunks:
        return 0

    provider = get_embeddings_provider()
    all_vectors: list[list[float]] = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c.chunk_text for c in batch]
        vectors = provider.embed(texts)
        all_vectors.extend(vectors)

    return store_chunks(session, chunks, all_vectors)
