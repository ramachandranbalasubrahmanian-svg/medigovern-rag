"""Canonical metadata model (implementation plan section 5.2)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SourceSystem(str, Enum):
    POLICY_PDF = "policy_pdf"
    GUIDELINE = "guideline"
    PLAN_BENEFIT = "plan_benefit"
    FHIR = "fhir"
    PROVIDER_DIR = "provider_dir"
    CLAIMS = "claims"


class DocumentType(str, Enum):
    MEDICAL_POLICY = "medical_policy"
    CLINICAL_GUIDELINE = "clinical_guideline"
    BENEFIT_DOC = "benefit_doc"
    PATIENT_BUNDLE = "patient_bundle"
    PROVIDER_RECORD = "provider_record"
    CLAIM = "claim"


class Sensitivity(str, Enum):
    SYNTHETIC = "synthetic"
    PII = "pii"
    PHI = "phi"


class DQStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    QUARANTINED = "quarantined"


class DQFinding(BaseModel):
    """Result of a single data-quality rule evaluation."""

    rule_id: str
    rule_name: str
    severity: DQStatus
    message: str
    field: str | None = None


class DocumentMetadata(BaseModel):
    """Governance backbone metadata record for every ingested artifact."""

    document_id: UUID = Field(default_factory=uuid4)
    source_system: SourceSystem
    document_type: DocumentType
    title: str
    policy_id: str | None = None
    payer: str | None = None
    plan_id: str | None = None
    # None means the field was absent in the source — caught by completeness DQ rule
    effective_date: date | None = None
    expiry_date: date | None = None
    procedure_codes: list[str] = Field(default_factory=list)
    diagnosis_codes: list[str] = Field(default_factory=list)
    data_owner: str | None = None
    steward: str | None = None
    source_uri: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    sensitivity: Sensitivity = Sensitivity.SYNTHETIC
    dq_status: DQStatus = DQStatus.PASSED
    dq_findings: list[DQFinding] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DocumentMetadataCreate(BaseModel):
    """Input schema for creating metadata (without server-assigned fields)."""

    source_system: SourceSystem
    document_type: DocumentType
    title: str
    policy_id: str | None = None
    payer: str
    plan_id: str
    effective_date: date
    expiry_date: date | None = None
    procedure_codes: list[str] = Field(default_factory=list)
    diagnosis_codes: list[str] = Field(default_factory=list)
    data_owner: str
    steward: str | None = None
    source_uri: str
    sensitivity: Sensitivity = Sensitivity.SYNTHETIC


class DocumentMetadataUpdate(BaseModel):
    """Partial update for metadata fields."""

    title: str | None = None
    policy_id: str | None = None
    payer: str | None = None
    plan_id: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    procedure_codes: list[str] | None = None
    diagnosis_codes: list[str] | None = None
    data_owner: str | None = None
    steward: str | None = None
    dq_status: DQStatus | None = None
    dq_findings: list[DQFinding] | None = None
    version: int | None = None
