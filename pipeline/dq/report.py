"""DQ run report — summary model, JSON serialization, and console output."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.models.metadata import DQStatus
from pipeline.ingestion.base import IngestedDocument


@dataclass
class DocumentSummary:
    document_id: str
    title: str
    source_uri: str
    dq_status: str
    findings: list[dict]


@dataclass
class DQReport:
    run_at: str
    total: int
    passed: int
    warning: int
    quarantined: int
    errors: list[str]
    findings_by_rule: dict[str, int]
    documents: list[DocumentSummary] = field(default_factory=list)

    @classmethod
    def from_documents(
        cls,
        documents: list[IngestedDocument],
        errors: list[str] | None = None,
    ) -> "DQReport":
        passed = sum(1 for d in documents if d.metadata.dq_status == DQStatus.PASSED)
        warning = sum(1 for d in documents if d.metadata.dq_status == DQStatus.WARNING)
        quarantined = sum(
            1 for d in documents if d.metadata.dq_status == DQStatus.QUARANTINED
        )

        findings_by_rule: dict[str, int] = {}
        for doc in documents:
            for f in doc.metadata.dq_findings:
                findings_by_rule[f.rule_id] = findings_by_rule.get(f.rule_id, 0) + 1

        doc_summaries = [
            DocumentSummary(
                document_id=str(doc.metadata.document_id),
                title=doc.metadata.title,
                source_uri=doc.metadata.source_uri,
                dq_status=doc.metadata.dq_status.value,
                findings=[f.model_dump() for f in doc.metadata.dq_findings],
            )
            for doc in documents
        ]

        return cls(
            run_at=datetime.now(timezone.utc).isoformat(),
            total=len(documents),
            passed=passed,
            warning=warning,
            quarantined=quarantined,
            errors=errors or [],
            findings_by_rule=findings_by_rule,
            documents=doc_summaries,
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("  MediGovern RAG — DQ Report")
        print("=" * 60)
        print(f"  Run at   : {self.run_at}")
        print(f"  Total    : {self.total}")
        print(f"  Passed   : {self.passed}")
        print(f"  Warning  : {self.warning}")
        print(f"  Quarant. : {self.quarantined}")
        if self.errors:
            print(f"  Errors   : {len(self.errors)}")
        print()
        if self.findings_by_rule:
            print("  Findings by rule:")
            for rule_id, count in sorted(self.findings_by_rule.items()):
                print(f"    {rule_id:<50} {count:>3}")
        print()
        quarantined_docs = [d for d in self.documents if d.dq_status == "quarantined"]
        if quarantined_docs:
            print("  Quarantined documents:")
            for doc in quarantined_docs:
                print(f"    [{doc.dq_status.upper()}] {doc.title}")
                for f in doc.findings:
                    sev = f.get("severity", "")
                    msg = f.get("message", "")
                    print(f"      • ({sev}) {msg}")
        warned_docs = [d for d in self.documents if d.dq_status == "warning"]
        if warned_docs:
            print("\n  Warning documents:")
            for doc in warned_docs:
                print(f"    [{doc.dq_status.upper()}] {doc.title}")
                for f in doc.findings:
                    sev = f.get("severity", "")
                    msg = f.get("message", "")
                    print(f"      • ({sev}) {msg}")
        print("=" * 60 + "\n")
