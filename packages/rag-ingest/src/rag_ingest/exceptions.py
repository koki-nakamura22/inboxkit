from __future__ import annotations


class RagIngestError(Exception):
    """Base exception for rag-ingest."""


class ConfigurationError(RagIngestError):
    """Raised when an Ingester subclass is missing required attributes."""
