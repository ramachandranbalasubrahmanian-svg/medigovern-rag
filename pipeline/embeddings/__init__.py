"""Knowledge layer: chunking, embedding, and vector storage."""

from pipeline.embeddings.chunker import chunk_document, chunk_documents
from pipeline.embeddings.indexer import embed_and_store
from pipeline.embeddings.pipeline import IndexReport, ingest_and_index
from pipeline.embeddings.store import clear_index, store_chunks, upsert_documents

__all__ = [
    "chunk_document",
    "chunk_documents",
    "embed_and_store",
    "ingest_and_index",
    "IndexReport",
    "clear_index",
    "store_chunks",
    "upsert_documents",
]
