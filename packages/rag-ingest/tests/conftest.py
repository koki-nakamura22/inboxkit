from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import pytest

from rag_ingest._upstream import Item
from rag_ingest.types import Chunk, IngestContext, Vector

_NO_LOADABLE_EXTENSIONS = (
    "interpreter was built without --enable-loadable-sqlite-extensions, "
    "so sqlite-vec cannot be loaded (python.org / GitHub macOS builds)"
)


def _supports_loadable_extensions() -> bool:
    """Whether this interpreter's sqlite3 can load extensions at all.

    CPython disables loadable SQLite extensions unless configured with
    `--enable-loadable-sqlite-extensions`; the python.org macOS framework
    builds (which `actions/setup-python` installs) leave it off, so
    `sqlite3.Connection` has no `enable_load_extension` attribute there.
    """
    if not hasattr(sqlite3.Connection, "enable_load_extension"):
        return False
    conn = sqlite3.connect(":memory:")
    try:
        conn.enable_load_extension(True)
    except (AttributeError, sqlite3.Error):
        return False
    else:
        return True
    finally:
        conn.close()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip `needs_sqlite_vec` tests when the interpreter cannot load extensions.

    The marker already existed and was applied throughout the suite, but nothing
    ever acted on it, so these tests failed instead of being skipped on such
    interpreters. `-ra` keeps the skip reason visible in the summary rather than
    letting the lost coverage pass unnoticed.
    """
    if _supports_loadable_extensions():
        return
    skip = pytest.mark.skip(reason=_NO_LOADABLE_EXTENSIONS)
    for item in items:
        if "needs_sqlite_vec" in item.keywords:
            item.add_marker(skip)


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
        default_factory=lambda: []
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
