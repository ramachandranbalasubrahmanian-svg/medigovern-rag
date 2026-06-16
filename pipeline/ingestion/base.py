"""Abstract loader interface and shared IngestedDocument type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.models.metadata import DocumentMetadata


@dataclass
class IngestedDocument:
    """Carrier for a single extracted artifact, before DQ scoring."""

    metadata: DocumentMetadata
    raw_content: str = ""
    # Loader-specific extras not in the canonical model (e.g. pa_required, npi)
    extra: dict = field(default_factory=dict)


class BaseLoader(ABC):
    """Abstract base for all source-type loaders."""

    @abstractmethod
    def can_load(self, path: Path) -> bool:
        """Return True when this loader handles the given file path."""

    @abstractmethod
    def load(self, path: Path) -> list[IngestedDocument]:
        """Parse the file and return one or more IngestedDocuments."""
