"""Run the full ingestion pipeline and print the DQ report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.ingestion.pipeline import run

REPORT_PATH = ROOT / "data" / "generated" / "dq_report.json"


def main() -> None:
    print("Running MediGovern RAG ingestion pipeline...")
    documents, report = run()
    report.print_summary()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report.to_json(), encoding="utf-8")
    print(f"Full report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
