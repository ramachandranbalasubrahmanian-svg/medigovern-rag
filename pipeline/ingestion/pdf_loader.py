"""Loader for synthetic payer-policy PDFs."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pypdf

from app.models.metadata import (
    DocumentMetadata,
    DocumentType,
    Sensitivity,
    SourceSystem,
)
from pipeline.ingestion.base import BaseLoader, IngestedDocument

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CPT_RE = re.compile(r"^\d{5}$")
_ICD_RE = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")


def _extract_field(text: str, label: str) -> str | None:
    m = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    from datetime import datetime

    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_codes(s: str | None) -> list[str]:
    if not s:
        return []
    return [c.strip() for c in re.split(r"[,\s]+", s) if c.strip()]


class PolicyPDFLoader(BaseLoader):
    """Loads synthetic payer medical policy PDFs."""

    def can_load(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def load(self, path: Path) -> list[IngestedDocument]:
        text = self._extract_text(path)
        metadata, extra = self._parse(text, path)
        return [IngestedDocument(metadata=metadata, raw_content=text, extra=extra)]

    def _extract_text(self, path: Path) -> str:
        reader = pypdf.PdfReader(str(path))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )

    def _parse(self, text: str, path: Path) -> tuple[DocumentMetadata, dict]:
        policy_id = _extract_field(text, "Policy ID")
        payer = _extract_field(text, "Payer")
        plan_id = _extract_field(text, "Plan ID")
        title = _extract_field(text, "Title") or path.stem
        data_owner = _extract_field(text, "Data Owner") or "clinical_policy_team"
        effective_date = _parse_date(_extract_field(text, "Effective Date"))
        expiry_date = _parse_date(_extract_field(text, "Expiry Date"))
        procedure_codes = _parse_codes(_extract_field(text, "Procedure Codes"))
        diagnosis_codes = _parse_codes(_extract_field(text, "Diagnosis Codes"))
        pa_required = _extract_field(text, "PA Required")

        metadata = DocumentMetadata(
            source_system=SourceSystem.POLICY_PDF,
            document_type=DocumentType.MEDICAL_POLICY,
            title=title,
            policy_id=policy_id,
            payer=payer,
            plan_id=plan_id,
            effective_date=effective_date,
            expiry_date=expiry_date,
            procedure_codes=procedure_codes,
            diagnosis_codes=diagnosis_codes,
            data_owner=data_owner,
            source_uri=str(path),
            sensitivity=Sensitivity.SYNTHETIC,
        )
        return metadata, {"pa_required": pa_required}
