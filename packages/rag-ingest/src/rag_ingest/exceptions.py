from __future__ import annotations


class RagIngestError(Exception):
    """Base exception for rag-ingest."""


class ConfigurationError(RagIngestError):
    """Raised when an Ingester subclass is missing required attributes."""


class EmbeddingError(RagIngestError):
    """Raised when embedding fails for one or more chunks."""

    def __init__(self, message: str, failed_indices: list[int] | None = None) -> None:
        super().__init__(message)
        self.failed_indices: list[int] = failed_indices if failed_indices is not None else []


class VectorSinkError(RagIngestError):
    """Base exception for vector sink failures."""


class SqliteVecLoadError(VectorSinkError):
    """Raised when sqlite-vec extension fails to load."""
