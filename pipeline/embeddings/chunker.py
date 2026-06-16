"""Policy-aware document chunking with clause-boundary preservation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings
from app.models.chunk import DocumentChunk
from app.models.metadata import DocumentType
from pipeline.ingestion.base import IngestedDocument

_POLICY_TYPES = {
    DocumentType.MEDICAL_POLICY,
    DocumentType.CLINICAL_GUIDELINE,
    DocumentType.BENEFIT_DOC,
}

# Section headers used in synthetic policy PDFs — split here to preserve clauses
_POLICY_SECTION_HEADERS = (
    "PRIOR AUTHORIZATION REQUIREMENTS",
    "REGULATORY NOTE",
    "COVERAGE CRITERIA",
    "MEDICAL NECESSITY",
    "EXCLUSIONS",
    "DEFINITIONS",
)

_HEADER_LINE_RE = re.compile(
    r"^(" + "|".join(re.escape(h) for h in _POLICY_SECTION_HEADERS) + r")\s*$",
    re.MULTILINE | re.IGNORECASE,
)


@dataclass
class ChunkerConfig:
    max_chars: int = 1200
    min_chars: int = 80


def chunk_documents(
    documents: list[IngestedDocument],
    config: ChunkerConfig | None = None,
) -> list[DocumentChunk]:
    """Chunk a list of ingested documents into DocumentChunk objects."""
    cfg = config or ChunkerConfig(max_chars=get_settings().chunk_max_chars)
    chunks: list[DocumentChunk] = []
    for doc in documents:
        chunks.extend(chunk_document(doc, cfg))
    return chunks


def chunk_document(
    doc: IngestedDocument,
    config: ChunkerConfig | None = None,
) -> list[DocumentChunk]:
    """Split one document into chunks with lineage metadata attached."""
    cfg = config or ChunkerConfig(max_chars=get_settings().chunk_max_chars)
    text = (doc.raw_content or "").strip()
    if not text:
        return []

    if doc.metadata.document_type in _POLICY_TYPES:
        sections = _split_policy_sections(text)
    else:
        sections = _split_paragraphs(text)

    pieces = _size_sections(sections, cfg.max_chars, cfg.min_chars)
    return [
        _make_chunk(doc, idx, piece_text, label)
        for idx, (piece_text, label) in enumerate(pieces)
    ]


def _make_chunk(
    doc: IngestedDocument,
    index: int,
    text: str,
    section_label: str | None,
) -> DocumentChunk:
    meta = doc.metadata
    return DocumentChunk(
        document_id=meta.document_id,
        source_uri=meta.source_uri,
        chunk_index=index,
        chunk_text=text.strip(),
        section_label=section_label,
        policy_id=meta.policy_id,
        payer=meta.payer,
        plan_id=meta.plan_id,
        effective_date=meta.effective_date,
        expiry_date=meta.expiry_date,
        procedure_codes=list(meta.procedure_codes),
        diagnosis_codes=list(meta.diagnosis_codes),
        dq_status=meta.dq_status,
        document_type=meta.document_type,
        source_system=meta.source_system,
    )


def _split_policy_sections(text: str) -> list[tuple[str, str | None]]:
    """Split policy text at known section headers, preserving clause boundaries."""
    matches = list(_HEADER_LINE_RE.finditer(text))
    if not matches:
        return [(text, None)]

    sections: list[tuple[str, str | None]] = []

    # Preamble before first header
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append((preamble, "Preamble"))

    for i, match in enumerate(matches):
        label = match.group(1).upper()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((body, label))

    return sections or [(text, None)]


def _split_paragraphs(text: str) -> list[tuple[str, str | None]]:
    """Split non-policy documents on blank lines."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [(p, None) for p in parts] or [(text, None)]


def _size_sections(
    sections: list[tuple[str, str | None]],
    max_chars: int,
    min_chars: int,
) -> list[tuple[str, str | None]]:
    """Merge small sections and split oversized ones while keeping labels."""
    merged: list[tuple[str, str | None]] = []
    buffer = ""
    buffer_label: str | None = None

    def flush() -> None:
        nonlocal buffer, buffer_label
        if buffer.strip():
            merged.append((buffer.strip(), buffer_label))
        buffer = ""
        buffer_label = None

    for text, label in sections:
        if len(text) > max_chars:
            flush()
            merged.extend(_hard_split(text, label, max_chars))
            continue

        candidate = f"{buffer}\n\n{text}".strip() if buffer else text
        if buffer and len(candidate) > max_chars:
            flush()
            buffer = text
            buffer_label = label
        elif buffer and len(text) < min_chars:
            buffer = candidate
        else:
            if not buffer:
                buffer = text
                buffer_label = label
            else:
                flush()
                buffer = text
                buffer_label = label

    flush()
    return merged


def _hard_split(
    text: str, label: str | None, max_chars: int
) -> list[tuple[str, str | None]]:
    """Split long text at sentence boundaries when section exceeds max_chars."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[tuple[str, str | None]] = []
    current = ""
    part = 0

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars and current:
            pieces.append((current, f"{label} (part {part + 1})" if label else None))
            part += 1
            current = sentence
        else:
            current = candidate

    if current:
        pieces.append((current, f"{label} (part {part + 1})" if part and label else label))

    return pieces or [(text, label)]
