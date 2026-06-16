"""Ingestion pipeline: scan data/raw/, load all sources, run DQ, produce report."""

from __future__ import annotations

from pathlib import Path

from pipeline.dq.engine import DQEngine
from pipeline.dq.report import DQReport
from pipeline.ingestion.base import BaseLoader, IngestedDocument
from pipeline.ingestion.csv_loader import ClaimsLoader, ProviderDirLoader
from pipeline.ingestion.fhir_loader import FHIRBundleLoader
from pipeline.ingestion.pdf_loader import PolicyPDFLoader

DEFAULT_LOADERS: list[BaseLoader] = [
    PolicyPDFLoader(),
    ProviderDirLoader(),
    ClaimsLoader(),
    FHIRBundleLoader(),
]

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def run(
    raw_dir: Path = RAW_DIR,
    loaders: list[BaseLoader] | None = None,
    dq_engine: DQEngine | None = None,
) -> tuple[list[IngestedDocument], DQReport]:
    """Load all files under raw_dir, apply DQ, return documents + report."""
    active_loaders = loaders or DEFAULT_LOADERS
    engine = dq_engine or DQEngine()

    documents: list[IngestedDocument] = []
    errors: list[str] = []

    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file():
            continue
        matched = False
        for loader in active_loaders:
            if loader.can_load(path):
                try:
                    docs = loader.load(path)
                    documents.extend(docs)
                    matched = True
                    break
                except Exception as exc:
                    errors.append(f"{path}: {exc}")
                    break
        if not matched and path.suffix.lower() not in (".gitkeep", ".md"):
            pass  # silently skip unknown file types

    documents = engine.run(documents)
    report = DQReport.from_documents(documents, errors=errors)
    return documents, report
