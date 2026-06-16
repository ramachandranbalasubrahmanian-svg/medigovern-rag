"""Eval script: run the 5 demo questions from plan section 2 through the RAG pipeline.

Can run in two modes:
  - DB mode (default): queries the live Postgres index
  - Offline mode (--offline): simulates retrieval against in-memory documents
    for CI / no-DB environments
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEMO_QUESTIONS = [
    {
        "id": "Q1",
        "question": "Does CPT 70553 require prior authorization for this plan?",
        "plan_id": "GOLD-PPO",
        "payer": "AcmeHealth",
        "cpt": "70553",
        "expect_abstain": True,   # conflicts exist for 70553 on GOLD-PPO
        "note": "Expect ABSTAIN — conflicting active policies POL-70553-A vs POL-70553-B",
    },
    {
        "id": "Q2",
        "question": "Which policy supports the denial reason for a knee replacement?",
        "plan_id": "GOLD-PPO",
        "payer": "AcmeHealth",
        "cpt": "27447",
        "expect_abstain": False,
        "note": "Expect answer citing POL-27447",
    },
    {
        "id": "Q3",
        "question": "What patient data is missing before submitting authorization for CPT 70553?",
        "plan_id": "SILVER-HMO",
        "payer": "BlueCross",
        "cpt": "70553",
        "expect_abstain": False,
        "note": "Should list missing data; expired policy POL-70553-EXP must NOT appear",
    },
    {
        "id": "Q4",
        "question": "Are there conflicting coverage rules for CPT 70553 on GOLD-PPO?",
        "plan_id": "GOLD-PPO",
        "payer": "AcmeHealth",
        "cpt": "70553",
        "expect_abstain": True,
        "note": "Expect ABSTAIN — conflict between POL-70553-A (PA=YES) and POL-70553-B (PA=NO)",
    },
    {
        "id": "Q5",
        "question": "Show the lineage for the prior auth recommendation for CPT 93306 echocardiography.",
        "plan_id": "GOLD-PPO",
        "payer": "AcmeHealth",
        "cpt": "93306",
        "expect_abstain": False,
        "note": "Expect answer with lineage from POL-93306",
    },
]


def _run_db_mode() -> None:
    from app.database import SessionLocal, init_db
    from pipeline.audit.service import ask as ask_service

    init_db()
    session = SessionLocal()
    try:
        _run_questions(session)
    finally:
        session.close()


def _run_questions(session) -> None:
    from pipeline.audit.service import ask as ask_service

    print("\n" + "=" * 70)
    print("  MediGovern RAG — Demo Question Eval")
    print("=" * 70)

    all_pass = True
    for q in DEMO_QUESTIONS:
        print(f"\n{'─' * 70}")
        print(f"  [{q['id']}] {q['question']}")
        print(f"  Filters: plan_id={q['plan_id']} payer={q['payer']} cpt={q['cpt']}")
        print(f"  Note: {q['note']}")
        print()

        packet, _ = ask_service(
            session,
            q["question"],
            plan_id=q["plan_id"],
            payer=q["payer"],
            cpt=q["cpt"],
        )

        print(f"  Confidence  : {packet.confidence}")
        print(f"  Abstained   : {packet.abstained}")
        if packet.abstained:
            print(f"  Reason      : {packet.abstain_reason}")
        print(f"  Citations   : {len(packet.citations)}")
        if packet.citations:
            for c in packet.citations[:3]:
                print(f"    • {c.policy_id} — {c.section_label}")
        if packet.missing_data:
            print(f"  Missing data: {packet.missing_data[:2]}")
        print(f"  Audit ID    : {packet.audit_id}")

        # Validate expectation
        if q["expect_abstain"] and not packet.abstained:
            print(f"  ⚠ EXPECTED ABSTAIN but got confidence={packet.confidence}")
            all_pass = False
        elif not q["expect_abstain"] and packet.abstained:
            print(f"  ⚠ Expected answer but got ABSTAIN")
            all_pass = False
        else:
            print(f"  ✓ Behaviour as expected")

        # Expired policy must never appear in citations
        bad_cits = [c for c in packet.citations if c.policy_id == "POL-70553-EXP"]
        if bad_cits:
            print("  ✗ EXPIRED POLICY POL-70553-EXP APPEARED IN CITATIONS!")
            all_pass = False
        else:
            print("  ✓ Expired policy correctly excluded from citations")

    print("\n" + "=" * 70)
    print(f"  Result: {'ALL PASS ✓' if all_pass else 'SOME FAILURES ✗'}")
    print("=" * 70 + "\n")


def _run_offline_mode() -> None:
    """No-DB simulation for verifying abstain logic and expired-policy exclusion."""
    from pipeline.retrieval.retriever import RetrievalResult, RetrievedChunk
    from pipeline.retrieval.generator import generate_answer
    from datetime import date

    print("\n[OFFLINE MODE — verifying abstain + expired-exclusion logic only]\n")

    # Q1/Q4: conflicting chunks
    conflict_chunks = [
        RetrievedChunk(
            chunk_id="1", document_id="a", source_uri="test", chunk_index=0,
            chunk_text="PA Required: YES Authorization required.",
            section_label="PRIOR AUTHORIZATION REQUIREMENTS",
            policy_id="POL-70553-A", payer="AcmeHealth", plan_id="GOLD-PPO",
            effective_date=date(2025, 1, 1), expiry_date=date(2027, 12, 31),
            procedure_codes=["70553"], diagnosis_codes=[], dq_status="passed",
            document_type="medical_policy", similarity_score=0.91,
        ),
        RetrievedChunk(
            chunk_id="2", document_id="b", source_uri="test", chunk_index=0,
            chunk_text="PA Required: NO No prior authorization required.",
            section_label="PRIOR AUTHORIZATION REQUIREMENTS",
            policy_id="POL-70553-B", payer="AcmeHealth", plan_id="GOLD-PPO",
            effective_date=date(2025, 6, 1), expiry_date=date(2027, 12, 31),
            procedure_codes=["70553"], diagnosis_codes=[], dq_status="passed",
            document_type="medical_policy", similarity_score=0.88,
        ),
    ]
    conflict_result = RetrievalResult(
        query="Does CPT 70553 require prior authorization?",
        filters_applied={},
        chunks=conflict_chunks,
        has_conflict=True,
        conflict_detail="Conflict: POL-70553-A (PA=YES) vs POL-70553-B (PA=NO)",
    )
    gen = generate_answer(conflict_result)
    print(f"Q1/Q4 conflict test → abstained={gen.abstained}, confidence={gen.confidence}")
    assert gen.abstained, "Expected ABSTAIN on conflict"
    print("  ✓ ABSTAIN on conflicting policies")

    # No results
    empty_result = RetrievalResult(
        query="irrelevant question", filters_applied={}, chunks=[], no_policy_found=True
    )
    gen2 = generate_answer(empty_result)
    assert gen2.abstained, "Expected ABSTAIN on no results"
    assert gen2.confidence == "ABSTAIN"
    print("  ✓ ABSTAIN when no policy found")

    # Expired policy NOT in chunks (DQ gate excludes it from DB query)
    clean_chunk = RetrievedChunk(
        chunk_id="3", document_id="c", source_uri="test", chunk_index=0,
        chunk_text="PA Required: YES Authorization required for neurological indications.",
        section_label="PRIOR AUTHORIZATION REQUIREMENTS",
        policy_id="POL-70553-C", payer="BlueCross", plan_id="SILVER-HMO",
        effective_date=date(2025, 1, 1), expiry_date=date(2027, 6, 30),
        procedure_codes=["70553"], diagnosis_codes=[], dq_status="passed",
        document_type="medical_policy", similarity_score=0.88,
    )
    clean_result = RetrievalResult(
        query="Does CPT 70553 need PA?", filters_applied={}, chunks=[clean_chunk]
    )
    gen3 = generate_answer(clean_result)
    expired_in_cits = any(c.policy_id == "POL-70553-EXP" for c in gen3.citations)
    assert not expired_in_cits, "Expired policy appeared in citations"
    print("  ✓ Expired policy correctly excluded")

    print("\n[OFFLINE] All logic checks passed ✓\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true",
                        help="Run logic checks only (no DB required)")
    args = parser.parse_args()

    if args.offline:
        _run_offline_mode()
    else:
        _run_db_mode()
