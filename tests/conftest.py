"""Pytest fixtures."""

import pytest
from datetime import date

from app.models.metadata import (
    DQFinding,
    DQStatus,
    DocumentMetadata,
    DocumentMetadataCreate,
    DocumentType,
    Sensitivity,
    SourceSystem,
)


@pytest.fixture
def sample_metadata_create() -> DocumentMetadataCreate:
    return DocumentMetadataCreate(
        source_system=SourceSystem.POLICY_PDF,
        document_type=DocumentType.MEDICAL_POLICY,
        title="MRI Brain Policy",
        policy_id="POL-70553",
        payer="Acme Health",
        plan_id="GOLD-PPO",
        effective_date=date(2025, 1, 1),
        expiry_date=date(2026, 12, 31),
        procedure_codes=["70553"],
        diagnosis_codes=["G43.909"],
        data_owner="clinical_policy_team",
        steward="policy_steward",
        source_uri="data/raw/policies/mri_brain.pdf",
        sensitivity=Sensitivity.SYNTHETIC,
    )


@pytest.fixture
def sample_metadata(sample_metadata_create: DocumentMetadataCreate) -> DocumentMetadata:
    return DocumentMetadata(**sample_metadata_create.model_dump())
