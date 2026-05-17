"""Performance tests: AC-P-001 - AC-P-004."""

from __future__ import annotations

import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from conftest import StubChunker, StubEmbedder, StubExtractor, StubSource, StubVectorSink
from rag_ingest._upstream import Item
from rag_ingest.ingester import Ingester
from rag_ingest.sinks.sqlite_vec import SQLiteVecSink
from rag_ingest.types import Chunk, IngestContext, Vector

_DIM = 4


def _make_ingest_context() -> IngestContext:
    return IngestContext(
        embedder_provider="stub",
        embedder_model="stub-bench",
        chunker_config={"chunk_size": 100},
        extractor_version="1.0",
        source_type="bench",
        extracted_at=datetime.now(tz=UTC),
    )


class _MultiChunkChunker:
    def __init__(self, count: int) -> None:
        self._count = count

    def chunk(self, text: str, item: Item) -> list[Chunk]:
        return [Chunk(text=f"{text[:8]}-{i}", chunk_index=i) for i in range(self._count)]

    @property
    def config(self) -> dict[str, Any]:
        return {"chunk_size": 100, "count": self._count}


class _MultiChunkEmbedder:
    def embed(self, chunks: list[Chunk]) -> list[Vector]:
        return [[0.1] * _DIM for _ in chunks]

    def dim(self) -> int:
        return _DIM

    @property
    def provider(self) -> str:
        return "stub"

    @property
    def model(self) -> str:
        return "stub-multi"


def _make_ingester(
    source: Any,
    sink: Any,
    chunker: Any = None,
    embedder: Any = None,
) -> Ingester:
    class _Ingester(Ingester):
        pass

    ing = _Ingester()
    ing.source = source
    ing.extractor = StubExtractor()
    ing.chunker = chunker or StubChunker()
    ing.embedder = embedder or StubEmbedder()
    ing.sink = sink  # type: ignore[assignment]
    return ing


# ── AC-P-001: framework pure overhead ≤ 200ms / Source ───────────────────────


@pytest.mark.slow
def test_overhead_per_source() -> None:
    items = [Item(id=f"item-{i}", payload=f"text-{i}") for i in range(100)]
    ingester = _make_ingester(StubSource(items=items), StubVectorSink())

    start = time.perf_counter()
    ingester.run()
    elapsed = time.perf_counter() - start

    assert (elapsed / 100) <= 0.200, f"per-source overhead {elapsed / 100:.4f}s > 200ms"


# ── AC-P-002: 10,000 chunks complete run + memory ≤ 500MB ────────────────────


@pytest.mark.slow
@pytest.mark.needs_sqlite_vec
def test_10k_chunks(tmp_path: Path) -> None:
    items = [Item(id=f"src-{i}", payload=f"text-{i}") for i in range(100)]
    sink = SQLiteVecSink(db_path=str(tmp_path / "rag.db"), dim=_DIM)
    ingester = _make_ingester(
        StubSource(items=items),
        sink,
        chunker=_MultiChunkChunker(count=100),
        embedder=_MultiChunkEmbedder(),
    )

    tracemalloc.start()
    result = ingester.run()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    total_bytes = sum(s.size for s in snapshot.statistics("filename"))
    assert result.processed_sources == 100
    assert result.chunk_count == 10_000
    assert result.failures == []
    assert total_bytes <= 500 * 1024 * 1024, f"memory {total_bytes / 1024**2:.1f}MB > 500MB"


# ── AC-P-003: SQLiteVecSink write 1,000 chunks ≤ 10s ─────────────────────────


@pytest.mark.slow
@pytest.mark.needs_sqlite_vec
def test_sink_write_1000_chunks(tmp_path: Path) -> None:
    sink = SQLiteVecSink(db_path=str(tmp_path / "rag.db"), dim=_DIM)
    item = Item(id="bench-src", payload="benchmark")
    chunks = [Chunk(text=f"chunk-{i}", chunk_index=i) for i in range(1000)]
    vectors: list[Vector] = [[0.1] * _DIM for _ in range(1000)]

    start = time.perf_counter()
    sink.write(chunks, vectors, item, _make_ingest_context())
    elapsed = time.perf_counter() - start

    assert elapsed <= 10.0, f"write 1,000 chunks took {elapsed:.2f}s > 10s"


# ── AC-P-004: dedup query + run with 1,000 pre-existing URIs ≤ 1s ─────────────


@pytest.mark.slow
@pytest.mark.needs_sqlite_vec
def test_dedup_query_performance(tmp_path: Path) -> None:
    db_path = str(tmp_path / "rag.db")
    seeder = SQLiteVecSink(db_path=db_path, dim=_DIM)
    ctx = _make_ingest_context()
    for i in range(1000):
        seeder.write(
            [Chunk(text="x", chunk_index=0)],
            [[0.1] * _DIM],
            Item(id=f"existing-{i}", payload="x"),
            ctx,
        )
    # release the connection so the second SQLiteVecSink can acquire a write lock
    seeder._conn.close()  # pyright: ignore[reportPrivateUsage]

    sink = SQLiteVecSink(db_path=db_path, dim=_DIM)
    ingester = _make_ingester(
        StubSource(items=[Item(id="new-1001", payload="fresh content")]),
        sink,
        embedder=_MultiChunkEmbedder(),  # default StubEmbedder と _DIM の dim 不一致を回避
    )

    start = time.perf_counter()
    result = ingester.run()
    elapsed = time.perf_counter() - start

    assert result.processed_sources == 1
    assert elapsed <= 1.0, f"dedup + run took {elapsed:.3f}s > 1s"
