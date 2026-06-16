"""Loaders for provider-directory and claims CSVs."""

from __future__ import annotations

import csv
from pathlib import Path

from app.models.metadata import (
    DocumentMetadata,
    DocumentType,
    Sensitivity,
    SourceSystem,
)
from pipeline.ingestion.base import BaseLoader, IngestedDocument


class ProviderDirLoader(BaseLoader):
    """Loads provider-directory CSV rows into provider-record documents."""

    def can_load(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv" and "provider" in path.stem.lower()

    def load(self, path: Path) -> list[IngestedDocument]:
        docs: list[IngestedDocument] = []
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                npi = row.get("npi", "").strip()
                name = row.get("provider_name", npi).strip()
                metadata = DocumentMetadata(
                    source_system=SourceSystem.PROVIDER_DIR,
                    document_type=DocumentType.PROVIDER_RECORD,
                    title=f"Provider {name}",
                    payer=None,
                    plan_id=None,
                    effective_date=None,
                    data_owner="provider_data_team",
                    source_uri=str(path),
                    sensitivity=Sensitivity.SYNTHETIC,
                )
                docs.append(
                    IngestedDocument(
                        metadata=metadata,
                        raw_content=str(dict(row)),
                        extra={
                            "npi": npi,
                            "provider_name": name,
                            "specialty": row.get("specialty", "").strip(),
                            "active": row.get("active", "true").strip().lower(),
                        },
                    )
                )
        return docs


class ClaimsLoader(BaseLoader):
    """Loads claims-like CSV rows."""

    def can_load(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv" and "claim" in path.stem.lower()

    def load(self, path: Path) -> list[IngestedDocument]:
        docs: list[IngestedDocument] = []
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                cpt = row.get("cpt_code", "").strip()
                icd = row.get("icd10_code", "").strip()
                metadata = DocumentMetadata(
                    source_system=SourceSystem.CLAIMS,
                    document_type=DocumentType.CLAIM,
                    title=f"Claim {row.get('claim_id', '')}",
                    payer=row.get("payer", "").strip() or None,
                    plan_id=row.get("plan_id", "").strip() or None,
                    effective_date=None,
                    procedure_codes=[cpt] if cpt else [],
                    diagnosis_codes=[icd] if icd else [],
                    data_owner="claims_data_team",
                    source_uri=str(path),
                    sensitivity=Sensitivity.SYNTHETIC,
                )
                docs.append(
                    IngestedDocument(
                        metadata=metadata,
                        raw_content=str(dict(row)),
                        extra={
                            "claim_id": row.get("claim_id", ""),
                            "member_id": row.get("member_id", ""),
                            "outcome": row.get("outcome", ""),
                            "service_date": row.get("service_date", ""),
                        },
                    )
                )
        return docs
