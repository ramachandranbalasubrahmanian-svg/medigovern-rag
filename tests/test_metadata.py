"""Unit tests for canonical metadata model."""

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


def test_document_metadata_create_valid(sample_metadata_create: DocumentMetadataCreate):
    assert sample_metadata_create.policy_id == "POL-70553"
    assert sample_metadata_create.procedure_codes == ["70553"]
    assert sample_metadata_create.sensitivity == Sensitivity.SYNTHETIC


def test_document_metadata_defaults(sample_metadata_create: DocumentMetadataCreate):
    meta = DocumentMetadata(**sample_metadata_create.model_dump())
    assert meta.document_id is not None
    assert meta.dq_status == DQStatus.PASSED
    assert meta.dq_findings == []
    assert meta.version == 1


def test_dq_finding_serialization():
    finding = DQFinding(
        rule_id="timeliness.expired",
        rule_name="Expired policy",
        severity=DQStatus.QUARANTINED,
        message="Policy expired on 2024-01-01",
        field="expiry_date",
    )
    meta = DocumentMetadata(
        source_system=SourceSystem.POLICY_PDF,
        document_type=DocumentType.MEDICAL_POLICY,
        title="Expired MRI Policy",
        payer="Acme Health",
        plan_id="GOLD-PPO",
        effective_date=date(2023, 1, 1),
        expiry_date=date(2024, 1, 1),
        data_owner="clinical_policy_team",
        source_uri="data/raw/policies/expired.pdf",
        dq_status=DQStatus.QUARANTINED,
        dq_findings=[finding],
    )
    assert meta.dq_findings[0].rule_id == "timeliness.expired"
    assert meta.dq_status == DQStatus.QUARANTINED


def test_source_system_enum_values():
    assert SourceSystem.FHIR.value == "fhir"
    assert DocumentType.PATIENT_BUNDLE.value == "patient_bundle"


def test_local_providers_without_api_keys():
    from app.providers.base import LocalEmbeddingsProvider, LocalLLMProvider

    llm = LocalLLMProvider()
    embeddings = LocalEmbeddingsProvider()
    assert "stub" in llm.generate("test prompt").lower()
    vectors = embeddings.embed(["hello", "world"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 8
