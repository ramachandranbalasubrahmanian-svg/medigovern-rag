"""DQ rule engine: applies all rules to a batch of documents."""

from __future__ import annotations

from app.models.metadata import DQStatus
from pipeline.dq.rules import DEFAULT_RULES, DQRule
from pipeline.ingestion.base import IngestedDocument


class DQEngine:
    """Applies a configurable set of DQ rules to a document batch."""

    def __init__(self, rules: list[DQRule] | None = None) -> None:
        self._rules = rules if rules is not None else DEFAULT_RULES

    def run(self, documents: list[IngestedDocument]) -> list[IngestedDocument]:
        """Score every document and update dq_status / dq_findings in-place."""
        for doc in documents:
            all_findings = []
            for rule in self._rules:
                all_findings.extend(rule.evaluate(doc, documents))

            doc.metadata.dq_findings = all_findings

            severities = {f.severity for f in all_findings}
            if DQStatus.QUARANTINED in severities:
                doc.metadata.dq_status = DQStatus.QUARANTINED
            elif DQStatus.WARNING in severities:
                doc.metadata.dq_status = DQStatus.WARNING
            else:
                doc.metadata.dq_status = DQStatus.PASSED

        return documents
