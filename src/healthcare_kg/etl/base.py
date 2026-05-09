from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from healthcare_kg.graph.neo4j_client import Neo4jClient


class BaseLoader(ABC):
    """Base class for all ontology ETL loaders."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    @abstractmethod
    def load(self, path: Path) -> dict[str, int]:
        """
        Parse the source file(s) at `path` and load into Neo4j.
        Returns a dict of counts, e.g. {"nodes": 1234, "relationships": 567}.
        """

    def _validate_path(self, path: Path, suffix: str | None = None) -> None:
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if suffix and path.is_file() and path.suffix.lower() != suffix.lower():
            raise ValueError(f"Expected a {suffix} file, got: {path.name}")
