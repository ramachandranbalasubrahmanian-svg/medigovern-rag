"""Generate all synthetic source data into data/raw/.

Seeded governance defects (required for DQ tests to pass):
  - POL-70553-EXP   : EXPIRED policy (expiry_date 2024-01-01)
  - POL-70553-A/B   : CONFLICTING PA requirement (same payer/plan/CPT, YES vs NO)
  - POL-NODATE      : MISSING effective_date
  - Provider CSV    : DUPLICATE NPI (1234567893 appears twice) + 2 INVALID NPIs
  - bundle-003.json : FHIR bundle MISSING diagnosis (patient context)
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
POLICIES_DIR = ROOT / "data" / "raw" / "policies"
PROVIDERS_DIR = ROOT / "data" / "raw" / "providers"
CLAIMS_DIR = ROOT / "data" / "raw" / "claims"
FHIR_DIR = ROOT / "data" / "raw" / "fhir"


# ---------------------------------------------------------------------------
# Policy PDF definitions
# ---------------------------------------------------------------------------

POLICIES = [
    # (filename, policy_id, payer, plan_id, cpt, icd_codes, effective, expiry, pa_required, extra_note)
    dict(
        filename="pol_70553_a.pdf",
        policy_id="POL-70553-A",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        cpt="70553",
        icd="G43.909, G35, R51.9",
        effective="2025-01-01",
        expiry="2027-12-31",
        pa_required="YES",
        title="Prior Authorization Policy - MRI Brain w/o and w/ Contrast (CPT 70553)",
        note="Authorization required. Prior imaging inconclusive or neurological symptoms documented.",
    ),
    # CONFLICT: same payer/plan/CPT as POL-70553-A but PA Required: NO
    dict(
        filename="pol_70553_b.pdf",
        policy_id="POL-70553-B",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        cpt="70553",
        icd="G43.909",
        effective="2025-06-01",
        expiry="2027-12-31",
        pa_required="NO",
        title="Coverage Policy - MRI Brain Contrast Study Amendment (CPT 70553)",
        note="[GOVERNANCE DEFECT SEEDED: CONFLICT] "
             "Amendment: PA not required for neurological indications — "
             "conflicts with POL-70553-A.",
    ),
    dict(
        filename="pol_70553_c.pdf",
        policy_id="POL-70553-C",
        payer="BlueCross",
        plan_id="SILVER-HMO",
        cpt="70553",
        icd="G43.909, R51.9",
        effective="2025-01-01",
        expiry="2027-06-30",
        pa_required="YES",
        title="Medical Policy - MRI Brain (CPT 70553)",
        note="Prior authorization required. Refer to clinical criteria checklist.",
    ),
    # EXPIRED
    dict(
        filename="pol_70553_exp.pdf",
        policy_id="POL-70553-EXP",
        payer="AcmeHealth",
        plan_id="BRONZE-EPO",
        cpt="70553",
        icd="G43.909",
        effective="2022-01-01",
        expiry="2024-01-01",
        pa_required="YES",
        title="[EXPIRED] Prior Auth Policy - MRI Brain BRONZE-EPO (CPT 70553)",
        note="[GOVERNANCE DEFECT SEEDED: EXPIRED] This policy expired 2024-01-01 "
             "and must be quarantined.",
    ),
    # MISSING effective_date — omit Effective Date line
    dict(
        filename="pol_nodate.pdf",
        policy_id="POL-NODATE",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        cpt="99213",
        icd="Z00.00",
        effective=None,          # <-- no effective date in PDF
        expiry="2027-12-31",
        pa_required="NO",
        title="[MISSING DATE] Coverage Policy - Office Visit Level 3 (CPT 99213)",
        note="[GOVERNANCE DEFECT SEEDED: MISSING EFFECTIVE DATE] "
             "Effective date omitted from this document.",
    ),
    dict(
        filename="pol_99213_a.pdf",
        policy_id="POL-99213-A",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        cpt="99213",
        icd="Z00.00",
        effective="2024-01-01",
        expiry="2027-12-31",
        pa_required="NO",
        title="Coverage Policy - Office Visit Level 3 (CPT 99213)",
        note="No prior authorization required for standard office visits.",
    ),
    dict(
        filename="pol_27447.pdf",
        policy_id="POL-27447",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        cpt="27447",
        icd="M17.11, M17.12",
        effective="2025-01-01",
        expiry="2027-12-31",
        pa_required="YES",
        title="Prior Auth Policy - Total Knee Arthroplasty (CPT 27447)",
        note="Conservative therapy failure documentation required.",
    ),
    dict(
        filename="pol_43239.pdf",
        policy_id="POL-43239",
        payer="BlueCross",
        plan_id="SILVER-HMO",
        cpt="43239",
        icd="K21.0, K57.30",
        effective="2025-01-01",
        expiry="2027-12-31",
        pa_required="YES",
        title="Prior Auth Policy - Upper GI Endoscopy with Biopsy (CPT 43239)",
        note="Endoscopy with biopsy requires prior authorization per plan guidelines.",
    ),
    dict(
        filename="pol_93306.pdf",
        policy_id="POL-93306",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        cpt="93306",
        icd="I25.10, I50.9",
        effective="2025-01-01",
        expiry="2027-12-31",
        pa_required="YES",
        title="Prior Auth Policy - Echocardiography Complete (CPT 93306)",
        note="Cardiology referral and clinical indication required.",
    ),
    dict(
        filename="pol_99214.pdf",
        policy_id="POL-99214",
        payer="BlueCross",
        plan_id="SILVER-HMO",
        cpt="99214",
        icd="Z00.00",
        effective="2024-06-01",
        expiry="2027-12-31",
        pa_required="NO",
        title="Coverage Policy - Office Visit Level 4 (CPT 99214)",
        note="No prior authorization required for established patient office visits.",
    ),
    dict(
        filename="pol_70450.pdf",
        policy_id="POL-70450",
        payer="AcmeHealth",
        plan_id="GOLD-PPO",
        cpt="70450",
        icd="R51.9, G89.29",
        effective="2025-01-01",
        expiry="2027-12-31",
        pa_required="YES",
        title="Prior Auth Policy - CT Head without Contrast (CPT 70450)",
        note="Clinical documentation of neurological symptoms required.",
    ),
    dict(
        filename="pol_71250.pdf",
        policy_id="POL-71250",
        payer="BlueCross",
        plan_id="SILVER-HMO",
        cpt="71250",
        icd="Z87.891, R04.2",
        effective="2025-01-01",
        expiry="2027-12-31",
        pa_required="YES",
        title="Prior Auth Policy - CT Thorax Low Dose (CPT 71250)",
        note="Lung cancer screening criteria: age 50-80, 20 pack-year history.",
    ),
]


def _make_pdf(path: Path, pol: dict) -> None:
    """Write a single policy PDF using reportlab."""
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]

    content = []

    content.append(Paragraph("SYNTHETIC PAYER MEDICAL POLICY", h1))
    content.append(
        Paragraph(
            "*** FOR DEMONSTRATION PURPOSES ONLY — NOT FOR CLINICAL USE ***", normal
        )
    )
    content.append(Spacer(1, 12))

    # Structured header fields — parsed by pdf_loader using labeled-line extraction
    header_lines = [
        f"Payer: {pol['payer']}",
        f"Plan ID: {pol['plan_id']}",
        f"Policy ID: {pol['policy_id']}",
        f"Title: {pol['title']}",
        f"Procedure Codes: {pol['cpt']}",
        f"Diagnosis Codes: {pol['icd']}",
        f"PA Required: {pol['pa_required']}",
        f"Data Owner: clinical_policy_team",
    ]
    if pol["effective"] is not None:
        header_lines.append(f"Effective Date: {pol['effective']}")
    if pol["expiry"]:
        header_lines.append(f"Expiry Date: {pol['expiry']}")

    for line in header_lines:
        content.append(Paragraph(line, normal))

    content.append(Spacer(1, 18))
    content.append(Paragraph("PRIOR AUTHORIZATION REQUIREMENTS", h2))
    content.append(Paragraph(pol["note"], normal))
    content.append(Spacer(1, 12))
    content.append(Paragraph("REGULATORY NOTE", h2))
    content.append(
        Paragraph(
            "This synthetic policy supports demonstration of CMS-0057-F compliance "
            "(effective 2024). Authorization decision timeframes: 72 hours (expedited) "
            "/ 7 calendar days (standard). All data is synthetic — no real PHI.",
            normal,
        )
    )

    doc.build(content)


# ---------------------------------------------------------------------------
# Provider directory CSV
# ---------------------------------------------------------------------------

def _generate_valid_npi(base9: str) -> str:
    """Given a 9-digit prefix, compute and append the valid Luhn check digit."""
    assert len(base9) == 9 and base9.isdigit()
    for check in range(10):
        candidate = base9 + str(check)
        full = [int(c) for c in "80840" + candidate]
        total = 0
        for i, d in enumerate(reversed(full)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        if total % 10 == 0:
            return candidate
    raise ValueError(f"No valid check digit found for base {base9!r}")


_NPI_BASES = [
    "123456789",  # → "1234567893" (verified)
    "987654321",  # → "9876543213" (verified)
    "111111111",  # computed at runtime
    "222222222",
    "333333333",
    "444444444",
    "555555555",
    "666666666",
    "777777777",
    "888888888",
    "100200300",
]

VALID_NPIS = [_generate_valid_npi(b) for b in _NPI_BASES]
# VALID_NPIS[0] = VALID_NPIS[1] = same NPI → DUPLICATE NPI defect
# (both use same base so same check digit)
_DUP_NPI = VALID_NPIS[0]  # "1234567893"
VALID_NPIS = [_DUP_NPI, _DUP_NPI] + VALID_NPIS[1:]   # first two entries are the duplicate pair

INVALID_NPIS = [
    "1234567890",  # fails Luhn
    "9999999999",  # fails Luhn
]

def _provider_rows() -> list[tuple]:
    rows = [
        (VALID_NPIS[0], "Dr. Alice Chen",    "Radiology",        "100 Main St",    "Springfield",     "IL", "62701", "true"),
        (VALID_NPIS[1], "Dr. Alice Chen",    "Radiology",        "100 Main St",    "Springfield",     "IL", "62701", "true"),  # duplicate
        (VALID_NPIS[2], "Dr. Bob Patel",     "Neurology",        "200 Oak Ave",    "Shelbyville",     "IL", "62565", "true"),
        (VALID_NPIS[3], "Dr. Carol Wu",      "Cardiology",       "300 Pine Rd",    "Capital City",    "IL", "62702", "true"),
        (VALID_NPIS[4], "Dr. David Kim",     "Internal Medicine","400 Elm Dr",     "Springfield",     "IL", "62703", "true"),
        (VALID_NPIS[5], "Dr. Eve Santos",    "Gastroenterology", "500 Maple Ln",   "Ogdenville",      "IL", "62704", "true"),
        (VALID_NPIS[6], "Dr. Frank Osei",    "Orthopedics",      "600 Cedar Blvd", "North Haverbrook","IL", "62705", "true"),
        (VALID_NPIS[7], "Dr. Grace Lee",     "Pulmonology",      "700 Birch Ct",   "Springfield",     "IL", "62706", "true"),
        (VALID_NPIS[8], "Dr. Hank Morris",   "Primary Care",     "800 Walnut Way", "Shelbyville",     "IL", "62707", "false"),
        (VALID_NPIS[9], "Dr. Irene Lopez",   "Oncology",         "900 Spruce St",  "Capital City",    "IL", "62708", "true"),
        (VALID_NPIS[10],"Dr. James Nguyen",  "Neurosurgery",     "1000 Aspen Ave", "Springfield",     "IL", "62709", "true"),
        # Explicit invalid NPIs
        (INVALID_NPIS[0], "Dr. Invalid One", "Unknown",          "11 Bad St",      "Nowhere",         "IL", "99999", "true"),
        (INVALID_NPIS[1], "Dr. Invalid Two", "Unknown",          "22 Bad Ave",     "Nowhere",         "IL", "99998", "true"),
    ]
    return rows


def _make_provider_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["npi", "provider_name", "specialty", "address", "city", "state", "zip", "active"]
        )
        writer.writerows(_provider_rows())


# ---------------------------------------------------------------------------
# Claims CSV
# ---------------------------------------------------------------------------

CLAIM_ROWS = [
    ("CLM-001", "MBR-101", "70553", "G43.909", "GOLD-PPO", "AcmeHealth", "APPROVED", "2025-03-15"),
    ("CLM-002", "MBR-102", "99213", "Z00.00",  "GOLD-PPO", "AcmeHealth", "APPROVED", "2025-03-20"),
    ("CLM-003", "MBR-103", "27447", "M17.11",  "SILVER-HMO", "BlueCross", "DENIED",  "2025-04-01"),
    ("CLM-004", "MBR-104", "93306", "I25.10",  "GOLD-PPO", "AcmeHealth", "PENDING", "2025-04-10"),
    ("CLM-005", "MBR-105", "43239", "K21.0",   "SILVER-HMO", "BlueCross", "APPROVED", "2025-04-12"),
    ("CLM-006", "MBR-106", "70450", "R51.9",   "GOLD-PPO", "AcmeHealth", "APPROVED", "2025-04-18"),
    ("CLM-007", "MBR-107", "71250", "Z87.891", "SILVER-HMO", "BlueCross", "APPROVED", "2025-05-02"),
]


def _make_claims_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["claim_id", "member_id", "cpt_code", "icd10_code", "plan_id", "payer", "outcome", "service_date"]
        )
        writer.writerows(CLAIM_ROWS)


# ---------------------------------------------------------------------------
# FHIR R4 patient bundles
# ---------------------------------------------------------------------------

BUNDLES = [
    {
        "filename": "patient_bundle_001.json",
        "id": "bundle-patient-001",
        "patient_id": "patient-001",
        "given": ["Jane"],
        "family": "SYNTHETIC",
        "gender": "female",
        "birthDate": "1972-07-04",
        "conditions": [
            {"id": "cond-001", "code": "G43.909", "display": "Migraine, unspecified"},
        ],
        "coverage": {"payor": "AcmeHealth", "class_value": "GOLD-PPO"},
    },
    {
        "filename": "patient_bundle_002.json",
        "id": "bundle-patient-002",
        "patient_id": "patient-002",
        "given": ["Robert"],
        "family": "SYNTHETIC",
        "gender": "male",
        "birthDate": "1958-11-20",
        "conditions": [
            {"id": "cond-002a", "code": "I25.10", "display": "Atherosclerotic heart disease"},
            {"id": "cond-002b", "code": "I50.9",  "display": "Heart failure, unspecified"},
        ],
        "coverage": {"payor": "AcmeHealth", "class_value": "GOLD-PPO"},
    },
    # MISSING DIAGNOSIS — patient context defect
    {
        "filename": "patient_bundle_003.json",
        "id": "bundle-patient-003",
        "patient_id": "patient-003",
        "given": ["Sam"],
        "family": "SYNTHETIC",
        "gender": "male",
        "birthDate": "1985-03-30",
        "conditions": [],   # <-- deliberate: no diagnosis codes
        "coverage": {"payor": "BlueCross", "class_value": "SILVER-HMO"},
        "_note": "GOVERNANCE DEFECT SEEDED: MISSING DIAGNOSIS",
    },
]


def _make_fhir_bundle(path: Path, spec: dict) -> None:
    entries = []

    # Patient
    entries.append(
        {
            "resource": {
                "resourceType": "Patient",
                "id": spec["patient_id"],
                "identifier": [
                    {"system": "http://example.org/synthetic/mrn", "value": spec["patient_id"]}
                ],
                "name": [{"family": spec["family"], "given": spec["given"]}],
                "gender": spec["gender"],
                "birthDate": spec["birthDate"],
                "_note": "SYNTHETIC — no real PHI",
            }
        }
    )

    # Conditions
    for cond in spec.get("conditions", []):
        entries.append(
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": cond["id"],
                    "subject": {"reference": f"Patient/{spec['patient_id']}"},
                    "code": {
                        "coding": [
                            {
                                "system": "http://hl7.org/fhir/sid/icd-10-cm",
                                "code": cond["code"],
                                "display": cond["display"],
                            }
                        ]
                    },
                    "clinicalStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                "code": "active",
                            }
                        ]
                    },
                }
            }
        )

    # Coverage
    cov = spec.get("coverage", {})
    if cov:
        entries.append(
            {
                "resource": {
                    "resourceType": "Coverage",
                    "id": f"coverage-{spec['patient_id']}",
                    "status": "active",
                    "beneficiary": {"reference": f"Patient/{spec['patient_id']}"},
                    "payor": [{"display": cov["payor"]}],
                    "class": [
                        {
                            "type": {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                                        "code": "plan",
                                    }
                                ]
                            },
                            "value": cov["class_value"],
                            "name": cov["class_value"],
                        }
                    ],
                }
            }
        )

    bundle = {
        "resourceType": "Bundle",
        "id": spec["id"],
        "type": "collection",
        "meta": {"tag": [{"display": "SYNTHETIC — for demonstration only"}]},
        "entry": entries,
    }
    if "_note" in spec:
        bundle["_governanceNote"] = spec["_note"]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_all(verbose: bool = True) -> None:
    POLICIES_DIR.mkdir(parents=True, exist_ok=True)

    for pol in POLICIES:
        pdf_path = POLICIES_DIR / pol["filename"]
        _make_pdf(pdf_path, pol)
        if verbose:
            note = ""
            if pol["effective"] is None:
                note = " [MISSING EFFECTIVE DATE]"
            if "EXP" in pol["policy_id"]:
                note = " [EXPIRED]"
            if pol["policy_id"] in ("POL-70553-A", "POL-70553-B"):
                note = " [CONFLICT PAIR]"
            print(f"  PDF  {pdf_path.name}{note}")

    provider_path = PROVIDERS_DIR / "provider_directory.csv"
    _make_provider_csv(provider_path)
    if verbose:
        print(f"  CSV  {provider_path.name}  [includes DUPLICATE NPI + 2 INVALID NPIs]")

    claims_path = CLAIMS_DIR / "claims.csv"
    _make_claims_csv(claims_path)
    if verbose:
        print(f"  CSV  {claims_path.name}")

    FHIR_DIR.mkdir(parents=True, exist_ok=True)
    for spec in BUNDLES:
        bundle_path = FHIR_DIR / spec["filename"]
        _make_fhir_bundle(bundle_path, spec)
        note = " [MISSING DIAGNOSIS]" if not spec.get("conditions") else ""
        if verbose:
            print(f"  JSON {bundle_path.name}{note}")

    if verbose:
        print("\nSynthetic data generation complete.")
        print("All data is SYNTHETIC. No real PHI is present.")


if __name__ == "__main__":
    print("Generating synthetic source data...")
    generate_all()
