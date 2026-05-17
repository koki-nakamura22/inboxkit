from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from rag_ingest._upstream import Item
from rag_ingest.types import Chunk, IngestContext, Vector


@runtime_checkable
class Chunker(Protocol):
    def chunk(self, text: str, item: Item) -> list[Chunk]: ...

    @property
    def config(self) -> dict[str, Any]: ...


@runtime_checkable
class Embedder(Protocol):
    def embed(self, chunks: list[Chunk]) -> list[Vector]: ...

    def dim(self) -> int: ...

    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...


@runtime_checkable
class VectorSink(Protocol):
    def write(
        self,
        chunks: list[Chunk],
        vectors: list[Vector],
        item: Item,
        ingest_context: IngestContext,
    ) -> None: ...

    def existing_source_uris(self) -> set[str]: ...
