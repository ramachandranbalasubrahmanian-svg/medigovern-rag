"""Tests proving each DQ rule fires on the seeded defects.

Each unit test builds IngestedDocument objects inline (no filesystem).
The integration test at the bottom runs the full pipeline over data/raw/
and asserts every seeded defect was caught.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.models.metadata import (
    DQStatus,
    DocumentMetadata,
    DocumentType,
    Sensitivity,
    SourceSystem,
)
from pipeline.dq.engine import DQEngine
from pipeline.dq.rules import (
    CompletenessRule,
    ConflictRule,
    PatientContextRule,
    TimelinessRule,
    UniquenessRule,
    ValidityRule,
    validate_npi,
)
from pipeline.ingestion.base import IngestedDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _policy(
    *,
    policy_id: str = "POL-TEST",
    payer: str | None = "AcmeHealth",
    plan_id: str | None = "GOLD-PPO",
    cpt: list[str] | None = None,
    icd: list[str] | None = None,
    effective: date | None = date(2025, 1, 1),
    expiry: date | None = None,
    pa_required: str | None = "YES",
    title: str = "Test Policy",
) -> IngestedDocument:
    return IngestedDocument(
        metadata=DocumentMetadata(
            source_system=SourceSystem.POLICY_PDF,
            document_type=DocumentType.MEDICAL_POLICY,
            title=title,
            policy_id=policy_id,
            payer=payer,
            plan_id=plan_id,
            effective_date=effective,
            expiry_date=expiry,
            procedure_codes=["70553"] if cpt is None else cpt,
            diagnosis_codes=["G43.909"] if icd is None else icd,
            data_owner="test_owner",
            source_uri="test://policy",
            sensitivity=Sensitivity.SYNTHETIC,
        ),
        extra={"pa_required": pa_required},
    )


def _provider(npi: str, name: str = "Dr. Test") -> IngestedDocument:
    return IngestedDocument(
        metadata=DocumentMetadata(
            source_system=SourceSystem.PROVIDER_DIR,
            document_type=DocumentType.PROVIDER_RECORD,
            title=f"Provider {name}",
            payer=None,
            plan_id=None,
            effective_date=None,
            data_owner="test",
            source_uri="test://provider",
            sensitivity=Sensitivity.SYNTHETIC,
        ),
        extra={"npi": npi, "provider_name": name},
    )


def _patient_bundle(diagnosis_codes: list[str]) -> IngestedDocument:
    return IngestedDocument(
        metadata=DocumentMetadata(
            source_system=SourceSystem.FHIR,
            document_type=DocumentType.PATIENT_BUNDLE,
            title="Test Bundle",
            payer="AcmeHealth",
            plan_id="GOLD-PPO",
            effective_date=None,
            diagnosis_codes=diagnosis_codes,
            data_owner="test",
            source_uri="test://fhir",
            sensitivity=Sensitivity.SYNTHETIC,
        ),
        extra={"has_diagnosis": bool(diagnosis_codes)},
    )


def _findings_with_rule(doc: IngestedDocument, rule_id_prefix: str) -> list:
    return [f for f in doc.metadata.dq_findings if f.rule_id.startswith(rule_id_prefix)]


# ---------------------------------------------------------------------------
# NPI validation unit tests
# ---------------------------------------------------------------------------

class TestNPIValidation:
    def test_known_valid_npi(self):
        assert validate_npi("1234567893") is True

    def test_known_valid_npi_2(self):
        assert validate_npi("9876543213") is True

    def test_invalid_npi_bad_checksum(self):
        assert validate_npi("1234567890") is False

    def test_invalid_npi_all_nines(self):
        assert validate_npi("9999999999") is False

    def test_invalid_npi_too_short(self):
        assert validate_npi("123456789") is False

    def test_invalid_npi_non_digits(self):
        assert validate_npi("123456789X") is False


# ---------------------------------------------------------------------------
# Completeness rule
# ---------------------------------------------------------------------------

class TestCompletenessRule:
    rule = CompletenessRule()

    def test_missing_effective_date_is_quarantined(self):
        doc = _policy(effective=None)
        findings = self.rule.evaluate(doc, [doc])
        assert any(f.rule_id == "completeness.missing_effective_date" for f in findings)
        assert any(f.severity == DQStatus.QUARANTINED for f in findings)

    def test_present_effective_date_passes(self):
        doc = _policy(effective=date(2025, 1, 1))
        findings = self.rule.evaluate(doc, [doc])
        assert not any(f.rule_id == "completeness.missing_effective_date" for f in findings)

    def test_missing_payer_quarantined(self):
        doc = _policy(payer=None)
        findings = self.rule.evaluate(doc, [doc])
        assert any(f.rule_id == "completeness.missing_payer" for f in findings)

    def test_missing_plan_id_quarantined(self):
        doc = _policy(plan_id=None)
        findings = self.rule.evaluate(doc, [doc])
        assert any(f.rule_id == "completeness.missing_plan_id" for f in findings)

    def test_empty_procedure_codes_is_warning(self):
        doc = _policy(cpt=[])
        findings = self.rule.evaluate(doc, [doc])
        assert any(
            f.rule_id == "completeness.empty_procedure_codes"
            and f.severity == DQStatus.WARNING
            for f in findings
        )

    def test_provider_record_skips_completeness(self):
        doc = _provider("1234567893")
        findings = self.rule.evaluate(doc, [doc])
        assert findings == []


# ---------------------------------------------------------------------------
# Validity rule — INVALID NPI caught
# ---------------------------------------------------------------------------

class TestValidityRule:
    rule = ValidityRule()

    def test_invalid_npi_caught(self):
        doc = _provider("1234567890")
        findings = self.rule.evaluate(doc, [doc])
        assert any(f.rule_id == "validity.invalid_npi" for f in findings)

    def test_valid_npi_passes(self):
        doc = _provider("1234567893")
        findings = self.rule.evaluate(doc, [doc])
        assert not any(f.rule_id == "validity.invalid_npi" for f in findings)

    def test_bad_cpt_pattern(self):
        doc = _policy(cpt=["7055X"])
        findings = self.rule.evaluate(doc, [doc])
        assert any(f.rule_id == "validity.bad_cpt" for f in findings)

    def test_valid_cpt_pattern(self):
        doc = _policy(cpt=["70553"])
        findings = self.rule.evaluate(doc, [doc])
        assert not any(f.rule_id == "validity.bad_cpt" for f in findings)

    def test_bad_icd_pattern(self):
        doc = _policy(icd=["not-valid"])
        findings = self.rule.evaluate(doc, [doc])
        assert any(f.rule_id == "validity.bad_icd10" for f in findings)

    def test_valid_icd_pattern(self):
        doc = _policy(icd=["G43.909"])
        findings = self.rule.evaluate(doc, [doc])
        assert not any(f.rule_id == "validity.bad_icd10" for f in findings)


# ---------------------------------------------------------------------------
# Timeliness rule — EXPIRED caught
# ---------------------------------------------------------------------------

class TestTimelinessRule:
    rule = TimelinessRule()

    def test_expired_policy_quarantined(self):
        yesterday = date.today() - timedelta(days=1)
        doc = _policy(expiry=yesterday)
        findings = self.rule.evaluate(doc, [doc])
        assert any(
            f.rule_id == "timeliness.expired" and f.severity == DQStatus.QUARANTINED
            for f in findings
        )

    def test_future_expiry_passes(self):
        next_year = date.today().replace(year=date.today().year + 1)
        doc = _policy(expiry=next_year)
        findings = self.rule.evaluate(doc, [doc])
        assert findings == []

    def test_no_expiry_passes(self):
        doc = _policy(expiry=None)
        findings = self.rule.evaluate(doc, [doc])
        assert findings == []


# ---------------------------------------------------------------------------
# Uniqueness rule — DUPLICATE NPI caught
# ---------------------------------------------------------------------------

class TestUniquenessRule:
    rule = UniquenessRule()

    def test_duplicate_npi_caught(self):
        npi = "1234567893"
        doc_a = _provider(npi, "Dr. Alice")
        doc_b = _provider(npi, "Dr. Alice (copy)")
        batch = [doc_a, doc_b]
        f_a = self.rule.evaluate(doc_a, batch)
        assert any(f.rule_id == "uniqueness.duplicate_npi" for f in f_a)

    def test_unique_npis_pass(self):
        doc_a = _provider("1234567893", "Dr. Alice")
        doc_b = _provider("9876543213", "Dr. Bob")
        batch = [doc_a, doc_b]
        assert not any(
            f.rule_id == "uniqueness.duplicate_npi" for f in self.rule.evaluate(doc_a, batch)
        )


# ---------------------------------------------------------------------------
# Conflict rule — CONFLICTING PA requirements caught
# ---------------------------------------------------------------------------

class TestConflictRule:
    rule = ConflictRule()

    def test_conflicting_pa_requirements_quarantined(self):
        pol_a = _policy(policy_id="POL-A", pa_required="YES")
        pol_b = _policy(policy_id="POL-B", pa_required="NO")
        batch = [pol_a, pol_b]
        f_a = self.rule.evaluate(pol_a, batch)
        f_b = self.rule.evaluate(pol_b, batch)
        assert any(f.rule_id == "consistency.conflict" for f in f_a), "POL-A should be flagged"
        assert any(f.rule_id == "consistency.conflict" for f in f_b), "POL-B should be flagged"

    def test_same_pa_requirement_no_conflict(self):
        pol_a = _policy(policy_id="POL-A", pa_required="YES")
        pol_b = _policy(policy_id="POL-B", pa_required="YES")
        batch = [pol_a, pol_b]
        assert not any(
            f.rule_id == "consistency.conflict" for f in self.rule.evaluate(pol_a, batch)
        )

    def test_different_plans_no_conflict(self):
        pol_a = _policy(policy_id="POL-A", plan_id="GOLD-PPO", pa_required="YES")
        pol_b = _policy(policy_id="POL-B", plan_id="SILVER-HMO", pa_required="NO")
        batch = [pol_a, pol_b]
        assert not any(
            f.rule_id == "consistency.conflict" for f in self.rule.evaluate(pol_a, batch)
        )

    def test_expired_policy_excluded_from_conflict(self):
        yesterday = date.today() - timedelta(days=1)
        pol_a = _policy(policy_id="POL-A", pa_required="YES")
        pol_expired = _policy(policy_id="POL-EXP", pa_required="NO", expiry=yesterday)
        batch = [pol_a, pol_expired]
        f_a = self.rule.evaluate(pol_a, batch)
        assert not any(f.rule_id == "consistency.conflict" for f in f_a), (
            "Expired policy should not trigger conflict"
        )


# ---------------------------------------------------------------------------
# Patient context rule — MISSING DIAGNOSIS caught
# ---------------------------------------------------------------------------

class TestPatientContextRule:
    rule = PatientContextRule()

    def test_missing_diagnosis_flagged(self):
        doc = _patient_bundle([])
        findings = self.rule.evaluate(doc, [doc])
        assert any(
            f.rule_id == "patient_context.missing_diagnosis" and f.severity == DQStatus.WARNING
            for f in findings
        )

    def test_present_diagnosis_passes(self):
        doc = _patient_bundle(["G43.909"])
        findings = self.rule.evaluate(doc, [doc])
        assert findings == []


# ---------------------------------------------------------------------------
# DQEngine integration (in-memory batch)
# ---------------------------------------------------------------------------

class TestDQEngine:
    def test_engine_sets_dq_status(self):
        expired = date.today() - timedelta(days=10)
        doc = _policy(expiry=expired)
        engine = DQEngine()
        results = engine.run([doc])
        assert results[0].metadata.dq_status == DQStatus.QUARANTINED

    def test_engine_warning_not_quarantined(self):
        doc = _provider("1234567890")  # invalid NPI → WARNING only
        engine = DQEngine()
        results = engine.run([doc])
        assert results[0].metadata.dq_status == DQStatus.WARNING

    def test_engine_clean_doc_passes(self):
        doc = _policy()
        engine = DQEngine()
        results = engine.run([doc])
        assert results[0].metadata.dq_status == DQStatus.PASSED


# ---------------------------------------------------------------------------
# Full-pipeline integration test: all seeded defects caught
# ---------------------------------------------------------------------------

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def _ensure_data_exists() -> bool:
    """Return True if synthetic data has been generated."""
    return (RAW_DIR / "policies").exists() and any(
        (RAW_DIR / "policies").glob("*.pdf")
    )


def _generate_data() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.generate_synthetic_data import generate_all
    generate_all(verbose=False)


@pytest.fixture(scope="module", autouse=True)
def ensure_synthetic_data():
    """Auto-generate synthetic data if not yet present."""
    if not _ensure_data_exists():
        _generate_data()


class TestFullPipelineSeededDefects:
    """Assert every seeded defect is caught by the full pipeline."""

    @pytest.fixture(scope="class")
    @classmethod
    def pipeline_results(cls):
        from pipeline.ingestion.pipeline import run
        documents, report = run(RAW_DIR)
        return documents, report

    def _by_policy_id(self, documents, policy_id: str):
        return next(
            (d for d in documents if d.metadata.policy_id == policy_id), None
        )

    def test_expired_policy_quarantined(self, pipeline_results):
        documents, _ = pipeline_results
        doc = self._by_policy_id(documents, "POL-70553-EXP")
        assert doc is not None, "POL-70553-EXP not found"
        assert doc.metadata.dq_status == DQStatus.QUARANTINED
        rule_ids = {f.rule_id for f in doc.metadata.dq_findings}
        assert "timeliness.expired" in rule_ids

    def test_conflicting_policies_quarantined(self, pipeline_results):
        documents, _ = pipeline_results
        pol_a = self._by_policy_id(documents, "POL-70553-A")
        pol_b = self._by_policy_id(documents, "POL-70553-B")
        assert pol_a is not None and pol_b is not None
        assert pol_a.metadata.dq_status == DQStatus.QUARANTINED
        assert pol_b.metadata.dq_status == DQStatus.QUARANTINED
        assert any(f.rule_id == "consistency.conflict" for f in pol_a.metadata.dq_findings)
        assert any(f.rule_id == "consistency.conflict" for f in pol_b.metadata.dq_findings)

    def test_missing_effective_date_quarantined(self, pipeline_results):
        documents, _ = pipeline_results
        doc = self._by_policy_id(documents, "POL-NODATE")
        assert doc is not None, "POL-NODATE not found"
        assert doc.metadata.dq_status == DQStatus.QUARANTINED
        rule_ids = {f.rule_id for f in doc.metadata.dq_findings}
        assert "completeness.missing_effective_date" in rule_ids

    def test_duplicate_npi_flagged(self, pipeline_results):
        documents, _ = pipeline_results
        dup_docs = [
            d for d in documents if d.extra.get("npi") == "1234567893"
        ]
        assert len(dup_docs) == 2, f"Expected 2 docs with NPI 1234567893, got {len(dup_docs)}"
        for doc in dup_docs:
            rule_ids = {f.rule_id for f in doc.metadata.dq_findings}
            assert "uniqueness.duplicate_npi" in rule_ids, (
                f"Duplicate NPI not flagged on: {doc.metadata.title}"
            )

    def test_invalid_npi_flagged(self, pipeline_results):
        documents, _ = pipeline_results
        invalid_npi_docs = [
            d
            for d in documents
            if d.extra.get("npi") in ("1234567890", "9999999999")
        ]
        assert len(invalid_npi_docs) == 2, (
            f"Expected 2 invalid-NPI docs, got {len(invalid_npi_docs)}"
        )
        for doc in invalid_npi_docs:
            rule_ids = {f.rule_id for f in doc.metadata.dq_findings}
            assert "validity.invalid_npi" in rule_ids

    def test_missing_diagnosis_bundle_flagged(self, pipeline_results):
        documents, _ = pipeline_results
        missing_diag = [
            d
            for d in documents
            if d.metadata.document_type == DocumentType.PATIENT_BUNDLE
            and not d.metadata.diagnosis_codes
        ]
        assert len(missing_diag) >= 1, "No patient bundle with missing diagnosis found"
        for doc in missing_diag:
            rule_ids = {f.rule_id for f in doc.metadata.dq_findings}
            assert "patient_context.missing_diagnosis" in rule_ids

    def test_report_totals_consistent(self, pipeline_results):
        _, report = pipeline_results
        assert report.total > 0
        assert report.passed + report.warning + report.quarantined == report.total
        assert report.quarantined >= 4  # expired, 2 conflicting, missing-date

    def test_valid_policies_pass(self, pipeline_results):
        documents, _ = pipeline_results
        valid_ids = {"POL-70553-C", "POL-27447", "POL-93306"}
        for pid in valid_ids:
            doc = self._by_policy_id(documents, pid)
            if doc:
                assert doc.metadata.dq_status == DQStatus.PASSED, (
                    f"{pid} should pass DQ but got {doc.metadata.dq_status}"
                )
