"""Loader for synthetic FHIR R4 patient bundles (JSON)."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.metadata import (
    DocumentMetadata,
    DocumentType,
    Sensitivity,
    SourceSystem,
)
from pipeline.ingestion.base import BaseLoader, IngestedDocument


class FHIRBundleLoader(BaseLoader):
    """Loads FHIR R4 Bundle JSON files."""

    def can_load(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
            return bundle.get("resourceType") == "Bundle"
        except Exception:
            return False

    def load(self, path: Path) -> list[IngestedDocument]:
        bundle = json.loads(path.read_text(encoding="utf-8"))
        entries = bundle.get("entry", [])
        resources = [e.get("resource", {}) for e in entries]

        patient = next(
            (r for r in resources if r.get("resourceType") == "Patient"), {}
        )
        conditions = [r for r in resources if r.get("resourceType") == "Condition"]
        coverage = next(
            (r for r in resources if r.get("resourceType") == "Coverage"), {}
        )

        patient_id = patient.get("id", bundle.get("id", "unknown"))
        patient_name = _patient_name(patient)

        diagnosis_codes = _extract_icd10(conditions)
        payer, plan_id = _extract_coverage(coverage)

        metadata = DocumentMetadata(
            source_system=SourceSystem.FHIR,
            document_type=DocumentType.PATIENT_BUNDLE,
            title=f"Patient Bundle {patient_id} — {patient_name}",
            payer=payer,
            plan_id=plan_id,
            effective_date=None,
            procedure_codes=[],
            diagnosis_codes=diagnosis_codes,
            data_owner="clinical_data_team",
            source_uri=str(path),
            sensitivity=Sensitivity.SYNTHETIC,
        )
        return [
            IngestedDocument(
                metadata=metadata,
                raw_content=json.dumps(bundle),
                extra={
                    "patient_id": patient_id,
                    "has_diagnosis": bool(diagnosis_codes),
                },
            )
        ]


def _patient_name(patient: dict) -> str:
    names = patient.get("name", [])
    if names:
        n = names[0]
        family = n.get("family", "SYNTHETIC")
        given = " ".join(n.get("given", []))
        return f"{given} {family}".strip()
    return "SYNTHETIC"


def _extract_icd10(conditions: list[dict]) -> list[str]:
    codes: list[str] = []
    for cond in conditions:
        for coding in cond.get("code", {}).get("coding", []):
            code = coding.get("code", "").strip()
            if code:
                codes.append(code)
    return codes


def _extract_coverage(coverage: dict) -> tuple[str | None, str | None]:
    if not coverage:
        return None, None
    payer_ref = coverage.get("payor", [{}])[0].get("display") if coverage.get("payor") else None
    plan_id = (
        coverage.get("class", [{}])[0].get("value")
        if coverage.get("class")
        else coverage.get("id")
    )
    return payer_ref, plan_id
