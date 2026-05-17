from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import pytest

from rag_ingest._upstream import Item
from rag_ingest.types import Chunk, IngestContext, Vector


@dataclass
class StubSource:
    items: list[Item] = field(default_factory=lambda: [Item(id="item-1", payload="hello world")])

    def fetch(self) -> Iterable[Item]:
        return self.items


@dataclass
class StubExtractor:
    def extract(self, item: Item) -> str:
        return str(item.payload)


@dataclass
class StubChunker:
    _config: dict[str, Any] = field(
        default_factory=lambda: {"chunk_size": 512, "overlap": 0, "unit": "tokens"}
    )
    call_count: int = field(default=0, init=False)

    def chunk(self, text: str, item: Item) -> list[Chunk]:
        self.call_count += 1
        return [Chunk(text=text, chunk_index=0, metadata={"source_id": item.id})]

    @property
    def config(self) -> dict[str, Any]:
        return self._config


@dataclass
class StubEmbedder:
    _provider: str = "stub"
    _model: str = "stub-model"
    call_count: int = field(default=0, init=False)

    def embed(self, chunks: list[Chunk]) -> list[Vector]:
        self.call_count += 1
        return [[0.1, 0.2, 0.3] for _ in chunks]

    def dim(self) -> int:
        return 3

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model


@dataclass
class StubVectorSink:
    write_calls: list[tuple[list[Chunk], list[Vector], Item, IngestContext]] = field(
        default_factory=list
    )

    def write(
        self,
        chunks: list[Chunk],
        vectors: list[Vector],
        item: Item,
        ingest_context: IngestContext,
    ) -> None:
        self.write_calls.append((chunks, vectors, item, ingest_context))

    def existing_source_uris(self) -> set[str]:
        return set()


@pytest.fixture
def stub_source() -> StubSource:
    return StubSource()


@pytest.fixture
def stub_extractor() -> StubExtractor:
    return StubExtractor()


@pytest.fixture
def stub_chunker() -> StubChunker:
    return StubChunker()


@pytest.fixture
def stub_embedder() -> StubEmbedder:
    return StubEmbedder()


@pytest.fixture
def stub_sink() -> StubVectorSink:
    return StubVectorSink()
