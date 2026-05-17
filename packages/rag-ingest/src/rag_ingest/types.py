from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Chunk:
    text: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=lambda: {})


Vector = list[float]


@dataclass
class IngestContext:
    embedder_provider: str
    embedder_model: str
    chunker_config: dict[str, Any]
    extractor_version: str
    source_type: str
    extracted_at: datetime
