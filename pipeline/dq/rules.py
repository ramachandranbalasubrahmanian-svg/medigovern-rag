"""Pluggable data-quality rules.  Each rule implements evaluate() and returns a
(possibly empty) list of DQFinding objects for a single document.

Cross-document rules (uniqueness, conflict) receive the full batch via all_docs.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date

from app.models.metadata import DQFinding, DQStatus, DocumentType

# Document types that must carry policy-style governance metadata
_POLICY_TYPES = {
    DocumentType.MEDICAL_POLICY,
    DocumentType.CLINICAL_GUIDELINE,
    DocumentType.BENEFIT_DOC,
}

_CPT_RE = re.compile(r"^\d{5}$")
_ICD_RE = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
_NPI_DIGITS_RE = re.compile(r"^\d{10}$")


def _luhn_check(digits: list[int]) -> bool:
    """Standard Luhn algorithm."""
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_npi(npi: str) -> bool:
    """NPI check-digit validation per CMS specification (Luhn on 80840+NPI)."""
    if not _NPI_DIGITS_RE.match(npi):
        return False
    full_digits = [int(c) for c in "80840" + npi]
    return _luhn_check(full_digits)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class DQRule(ABC):
    rule_id: str
    rule_name: str

    @abstractmethod
    def evaluate(
        self,
        doc: "IngestedDocument",  # type: ignore[name-defined]  # avoid circular import
        all_docs: "list[IngestedDocument]",
    ) -> list[DQFinding]:
        ...


# ---------------------------------------------------------------------------
# 1. Completeness
# ---------------------------------------------------------------------------

class CompletenessRule(DQRule):
    """Flag missing mandatory fields on policy-type documents."""

    rule_id = "completeness"
    rule_name = "Completeness check"

    def evaluate(self, doc, all_docs) -> list[DQFinding]:
        findings: list[DQFinding] = []
        meta = doc.metadata

        if meta.document_type not in _POLICY_TYPES:
            return findings

        if meta.effective_date is None:
            findings.append(
                DQFinding(
                    rule_id=f"{self.rule_id}.missing_effective_date",
                    rule_name=self.rule_name,
                    severity=DQStatus.QUARANTINED,
                    message="effective_date is missing — cannot determine policy currency",
                    field="effective_date",
                )
            )
        if not meta.payer:
            findings.append(
                DQFinding(
                    rule_id=f"{self.rule_id}.missing_payer",
                    rule_name=self.rule_name,
                    severity=DQStatus.QUARANTINED,
                    message="payer is missing",
                    field="payer",
                )
            )
        if not meta.plan_id:
            findings.append(
                DQFinding(
                    rule_id=f"{self.rule_id}.missing_plan_id",
                    rule_name=self.rule_name,
                    severity=DQStatus.QUARANTINED,
                    message="plan_id is missing",
                    field="plan_id",
                )
            )
        if not meta.procedure_codes:
            findings.append(
                DQFinding(
                    rule_id=f"{self.rule_id}.empty_procedure_codes",
                    rule_name=self.rule_name,
                    severity=DQStatus.WARNING,
                    message="procedure_codes is empty on a policy document",
                    field="procedure_codes",
                )
            )
        return findings


# ---------------------------------------------------------------------------
# 2. Validity
# ---------------------------------------------------------------------------

class ValidityRule(DQRule):
    """Validate NPI checksums and code-format patterns."""

    rule_id = "validity"
    rule_name = "Validity check"

    def evaluate(self, doc, all_docs) -> list[DQFinding]:
        findings: list[DQFinding] = []
        meta = doc.metadata
        npi: str = doc.extra.get("npi", "")

        if npi and not validate_npi(npi):
            findings.append(
                DQFinding(
                    rule_id=f"{self.rule_id}.invalid_npi",
                    rule_name=self.rule_name,
                    severity=DQStatus.WARNING,
                    message=f"NPI '{npi}' fails Luhn check-digit validation",
                    field="npi",
                )
            )

        for code in meta.procedure_codes:
            if not _CPT_RE.match(code):
                findings.append(
                    DQFinding(
                        rule_id=f"{self.rule_id}.bad_cpt",
                        rule_name=self.rule_name,
                        severity=DQStatus.WARNING,
                        message=f"CPT code '{code}' does not match 5-digit pattern",
                        field="procedure_codes",
                    )
                )

        for code in meta.diagnosis_codes:
            if not _ICD_RE.match(code):
                findings.append(
                    DQFinding(
                        rule_id=f"{self.rule_id}.bad_icd10",
                        rule_name=self.rule_name,
                        severity=DQStatus.WARNING,
                        message=f"ICD-10 code '{code}' does not match expected pattern",
                        field="diagnosis_codes",
                    )
                )

        return findings


# ---------------------------------------------------------------------------
# 3. Timeliness
# ---------------------------------------------------------------------------

class TimelinessRule(DQRule):
    """Flag policies whose expiry_date is in the past."""

    rule_id = "timeliness.expired"
    rule_name = "Timeliness check"

    def evaluate(self, doc, all_docs) -> list[DQFinding]:
        meta = doc.metadata
        if meta.expiry_date and meta.expiry_date < date.today():
            return [
                DQFinding(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=DQStatus.QUARANTINED,
                    message=f"Policy expired on {meta.expiry_date} — excluded from retrieval",
                    field="expiry_date",
                )
            ]
        return []


# ---------------------------------------------------------------------------
# 4. Uniqueness
# ---------------------------------------------------------------------------

class UniquenessRule(DQRule):
    """Flag duplicate NPIs and duplicate policy_id with different content."""

    rule_id = "uniqueness"
    rule_name = "Uniqueness check"

    def evaluate(self, doc, all_docs) -> list[DQFinding]:
        findings: list[DQFinding] = []
        meta = doc.metadata
        npi: str = doc.extra.get("npi", "")

        # Duplicate NPI: same NPI in any other provider record
        if npi:
            duplicates = [
                d
                for d in all_docs
                if d is not doc
                and d.extra.get("npi") == npi
            ]
            if duplicates:
                findings.append(
                    DQFinding(
                        rule_id=f"{self.rule_id}.duplicate_npi",
                        rule_name=self.rule_name,
                        severity=DQStatus.WARNING,
                        message=f"NPI '{npi}' appears in {len(duplicates) + 1} records — possible duplicate",
                        field="npi",
                    )
                )

        # Duplicate policy_id with differing procedure_codes
        if meta.policy_id:
            conflicts = [
                d
                for d in all_docs
                if d is not doc
                and d.metadata.policy_id == meta.policy_id
                and sorted(d.metadata.procedure_codes) != sorted(meta.procedure_codes)
            ]
            if conflicts:
                findings.append(
                    DQFinding(
                        rule_id=f"{self.rule_id}.duplicate_policy_id",
                        rule_name=self.rule_name,
                        severity=DQStatus.WARNING,
                        message=(
                            f"policy_id '{meta.policy_id}' exists in "
                            f"{len(conflicts)} other record(s) with different content"
                        ),
                        field="policy_id",
                    )
                )

        return findings


# ---------------------------------------------------------------------------
# 5. Consistency / Conflict
# ---------------------------------------------------------------------------

def _is_active_policy(doc: "IngestedDocument") -> bool:
    meta = doc.metadata
    if meta.document_type not in _POLICY_TYPES:
        return False
    if meta.expiry_date and meta.expiry_date < date.today():
        return False
    return True


class ConflictRule(DQRule):
    """Flag two active policies for the same payer+plan+CPT with opposite PA requirements."""

    rule_id = "consistency.conflict"
    rule_name = "PA requirement conflict"

    def evaluate(self, doc, all_docs) -> list[DQFinding]:
        if not _is_active_policy(doc):
            return []

        meta = doc.metadata
        pa: str | None = doc.extra.get("pa_required")
        if not pa:
            return []

        findings: list[DQFinding] = []
        for other in all_docs:
            if other is doc:
                continue
            if not _is_active_policy(other):
                continue
            other_pa: str | None = other.extra.get("pa_required")
            if not other_pa:
                continue
            if pa.upper() == other_pa.upper():
                continue

            # Same payer, plan, and at least one overlapping CPT code
            shared_cpts = set(meta.procedure_codes) & set(other.metadata.procedure_codes)
            if (
                meta.payer
                and meta.payer == other.metadata.payer
                and meta.plan_id
                and meta.plan_id == other.metadata.plan_id
                and shared_cpts
            ):
                findings.append(
                    DQFinding(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=DQStatus.QUARANTINED,
                        message=(
                            f"Conflicting PA requirement for CPT {sorted(shared_cpts)} "
                            f"between this policy (PA={pa}) and '{other.metadata.policy_id}' "
                            f"(PA={other_pa}) — human review required"
                        ),
                        field="pa_required",
                    )
                )

        return findings


# ---------------------------------------------------------------------------
# 6. Patient context
# ---------------------------------------------------------------------------

class PatientContextRule(DQRule):
    """Flag patient bundles missing diagnosis codes needed for medical necessity."""

    rule_id = "patient_context.missing_diagnosis"
    rule_name = "Patient context check"

    def evaluate(self, doc, all_docs) -> list[DQFinding]:
        from app.models.metadata import DocumentType

        if doc.metadata.document_type != DocumentType.PATIENT_BUNDLE:
            return []
        if not doc.metadata.diagnosis_codes:
            return [
                DQFinding(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=DQStatus.WARNING,
                    message=(
                        "Patient bundle has no diagnosis codes — "
                        "medical necessity cannot be evaluated"
                    ),
                    field="diagnosis_codes",
                )
            ]
        return []


# ---------------------------------------------------------------------------
# Default rule set
# ---------------------------------------------------------------------------

DEFAULT_RULES: list[DQRule] = [
    CompletenessRule(),
    ValidityRule(),
    TimelinessRule(),
    UniquenessRule(),
    ConflictRule(),
    PatientContextRule(),
]
