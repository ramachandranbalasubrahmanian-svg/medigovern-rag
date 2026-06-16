"""Run full ingest-and-index pipeline: load -> DQ -> chunk -> embed -> store."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.embeddings.pipeline import ingest_and_index

REPORT_PATH = ROOT / "data" / "generated" / "index_report.json"


def main() -> None:
    print("Running MediGovern RAG ingest-and-index pipeline...")
    report = ingest_and_index()

    if report.dq_report:
        report.dq_report.print_summary()

    report.print_summary()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "docs_ingested": report.docs_ingested,
        "docs_passed": report.docs_passed,
        "docs_warning": report.docs_warning,
        "docs_quarantined": report.docs_quarantined,
        "docs_indexed": report.docs_indexed,
        "chunks_embedded": report.chunks_embedded,
        "errors": report.errors,
    }
    REPORT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Index report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
