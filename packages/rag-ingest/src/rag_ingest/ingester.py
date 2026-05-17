from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from rag_ingest._upstream import Extractor, Source
from rag_ingest.exceptions import ConfigurationError
from rag_ingest.protocols import Chunker, Embedder, VectorSink
from rag_ingest.types import IngestContext

_REQUIRED_ATTRS = ("source", "extractor", "chunker", "embedder", "sink")


@dataclass
class RunResult:
    processed_sources: int = 0
    chunk_count: int = 0
    skipped_count: int = 0
    dry_run_chunks: int = 0
    failures: list[dict[str, Any]] = field(default_factory=lambda: [])


class Ingester(ABC):
    source: Source
    extractor: Extractor
    chunker: Chunker
    embedder: Embedder
    sink: VectorSink

    def run(
        self,
        *,
        force: bool = False,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> RunResult:
        # T201: minimum skeleton flow (dedup / full IngestContext / batch / transaction → T205)
        missing = [a for a in _REQUIRED_ATTRS if not hasattr(self, a)]
        if missing:
            raise ConfigurationError(f"Missing required attributes: {missing}")

        result = RunResult()
        items = list(self.source.fetch())
        if limit is not None:
            items = items[:limit]

        for item in items:
            try:
                text = self.extractor.extract(item)
                chunks = self.chunker.chunk(text, item)

                if dry_run:
                    result.dry_run_chunks += len(chunks)
                    result.processed_sources += 1
                    continue

                vectors = self.embedder.embed(chunks)
                ingest_context = IngestContext(
                    embedder_provider=self.embedder.provider,
                    embedder_model=self.embedder.model,
                    chunker_config=self.chunker.config,
                    extractor_version="0.0.0",  # T205 で実 Extractor から取得
                    source_type=type(self.source).__name__,
                    extracted_at=datetime.now(tz=timezone.utc),
                )
                self.sink.write(chunks, vectors, item, ingest_context)
                result.processed_sources += 1
                result.chunk_count += len(chunks)
            except Exception as exc:
                result.failures.append({"item": item, "error": str(exc)})

        return result
