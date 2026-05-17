"""Tests for Ingester.run(): AC-001 / 001b / 001c / 007 / 007b / R-003."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from conftest import StubChunker, StubEmbedder, StubExtractor, StubSource, StubVectorSink

from rag_ingest._upstream import Item
from rag_ingest.chunkers.fixed_size import FixedSizeChunker
from rag_ingest.exceptions import ConfigurationError
from rag_ingest.ingester import Ingester, RunResult
from rag_ingest.sinks.sqlite_vec import SQLiteVecSink
from rag_ingest.types import Chunk, IngestContext, Vector


class StubIngester(Ingester):
    def __init__(
        self,
        source: StubSource | None = None,
        sink: StubVectorSink | None = None,
        chunker: StubChunker | None = None,
        embedder: StubEmbedder | None = None,
    ) -> None:
        self.source = source or StubSource()
        self.extractor = StubExtractor()
        self.chunker = chunker or StubChunker()
        self.embedder = embedder or StubEmbedder()
        self.sink = sink or StubVectorSink()


@dataclass
class PreloadedSink:
    """StubVectorSink with pre-seeded existing URIs for dedup tests."""

    write_calls: list[tuple[list[Chunk], list[Vector], Item, IngestContext]] = field(
        default_factory=list
    )
    _existing: set[str] = field(default_factory=set)

    def write(
        self,
        chunks: list[Chunk],
        vectors: list[Vector],
        item: Item,
        ingest_context: IngestContext,
    ) -> None:
        self.write_calls.append((chunks, vectors, item, ingest_context))

    def existing_source_uris(self) -> set[str]:
        return set(self._existing)


def _make_e2e_ingester(
    source: StubSource,
    sink: SQLiteVecSink,
) -> Ingester:
    class E2EIngester(Ingester):
        pass

    ingester = E2EIngester()
    ingester.source = source
    ingester.extractor = StubExtractor()
    ingester.chunker = FixedSizeChunker(chunk_size=512, overlap=0, unit="char")
    ingester.embedder = StubEmbedder()
    ingester.sink = sink  # type: ignore[assignment]
    return ingester


# ── AC-001: normal flow ────────────────────────────────────────────────────────

def test_run_returns_run_result() -> None:
    result = StubIngester().run()
    assert isinstance(result, RunResult)


def test_run_processed_sources_equals_item_count() -> None:
    source = StubSource(items=[Item(id="a", payload="x"), Item(id="b", payload="y")])
    result = StubIngester(source=source).run()
    assert result.processed_sources == 2


def test_run_chunk_count_reflects_chunks() -> None:
    result = StubIngester().run()
    assert result.chunk_count == 1  # StubChunker returns 1 chunk per item


def test_run_sink_write_called_once_per_source() -> None:
    sink = StubVectorSink()
    source = StubSource(items=[Item(id="a", payload="x"), Item(id="b", payload="y")])
    StubIngester(source=source, sink=sink).run()
    assert len(sink.write_calls) == 2


def test_run_chunk_and_embed_both_called(
    stub_chunker: StubChunker, stub_embedder: StubEmbedder
) -> None:
    ingester = StubIngester(chunker=stub_chunker, embedder=stub_embedder)
    ingester.run()
    assert stub_chunker.call_count == 1
    assert stub_embedder.call_count == 1


def test_run_no_failures_on_success() -> None:
    result = StubIngester().run()
    assert result.failures == []


def test_run_skipped_count_zero_on_success() -> None:
    result = StubIngester().run()
    assert result.skipped_count == 0


def test_run_limit_restricts_item_count() -> None:
    source = StubSource(
        items=[Item(id=str(i), payload=f"text-{i}") for i in range(5)]
    )
    result = StubIngester(source=source).run(limit=2)
    assert result.processed_sources == 2


def test_run_limit_zero_processes_nothing() -> None:
    source = StubSource(items=[Item(id="a", payload="x")])
    result = StubIngester(source=source).run(limit=0)
    assert result.processed_sources == 0
    assert result.chunk_count == 0


def test_run_limit_larger_than_item_count_processes_all() -> None:
    source = StubSource(items=[Item(id=str(i), payload=f"x{i}") for i in range(3)])
    result = StubIngester(source=source).run(limit=100)
    assert result.processed_sources == 3


# ── AC-001b: IngestContext construction and propagation ────────────────────────

def test_run_ingest_context_carries_embedder_metadata() -> None:
    sink = StubVectorSink()
    StubIngester(sink=sink).run()
    _, _, _, ctx = sink.write_calls[0]
    assert ctx.embedder_provider == "stub"
    assert ctx.embedder_model == "stub-model"
    assert ctx.chunker_config == {"chunk_size": 512, "overlap": 0, "unit": "tokens"}


def test_run_ingest_context_extractor_version_defaults_to_unknown() -> None:
    sink = StubVectorSink()
    StubIngester(sink=sink).run()
    _, _, _, ctx = sink.write_calls[0]
    assert ctx.extractor_version == "unknown"


def test_run_ingest_context_extractor_version_from_version_attr() -> None:
    class VersionedExtractor(StubExtractor):
        version = "2.3.4"

    sink = StubVectorSink()
    ingester = StubIngester(sink=sink)
    ingester.extractor = VersionedExtractor()
    ingester.run()
    _, _, _, ctx = sink.write_calls[0]
    assert ctx.extractor_version == "2.3.4"


def test_run_ingest_context_source_type_uses_extractor_class_name() -> None:
    sink = StubVectorSink()
    StubIngester(sink=sink).run()
    _, _, _, ctx = sink.write_calls[0]
    assert ctx.source_type == "StubExtractor"


def test_run_ingest_context_source_type_from_source_type_attr() -> None:
    class TaggedExtractor(StubExtractor):
        source_type = "notion_page"

    sink = StubVectorSink()
    ingester = StubIngester(sink=sink)
    ingester.extractor = TaggedExtractor()
    ingester.run()
    _, _, _, ctx = sink.write_calls[0]
    assert ctx.source_type == "notion_page"


def test_run_ingest_context_extracted_at_is_utc_datetime() -> None:
    sink = StubVectorSink()
    StubIngester(sink=sink).run()
    _, _, _, ctx = sink.write_calls[0]
    assert isinstance(ctx.extracted_at, datetime)
    assert ctx.extracted_at.tzinfo is not None
    assert ctx.extracted_at.utcoffset() is not None
    assert ctx.extracted_at.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_run_ingest_context_extracted_at_is_iso8601_compatible() -> None:
    """extracted_at.isoformat() must produce a valid UTC ISO8601 string."""
    sink = StubVectorSink()
    StubIngester(sink=sink).run()
    _, _, _, ctx = sink.write_calls[0]
    iso = ctx.extracted_at.isoformat()
    assert "+00:00" in iso


# ── AC-001c: dry_run mode ──────────────────────────────────────────────────────

def test_dry_run_chunks_recorded() -> None:
    result = StubIngester().run(dry_run=True)
    assert result.dry_run_chunks == 1


def test_dry_run_processed_sources_not_incremented() -> None:
    result = StubIngester().run(dry_run=True)
    assert result.processed_sources == 0


def test_dry_run_embed_not_called(stub_embedder: StubEmbedder) -> None:
    StubIngester(embedder=stub_embedder).run(dry_run=True)
    assert stub_embedder.call_count == 0


def test_dry_run_sink_write_not_called() -> None:
    sink = StubVectorSink()
    StubIngester(sink=sink).run(dry_run=True)
    assert len(sink.write_calls) == 0


def test_dry_run_chunk_count_stays_zero() -> None:
    result = StubIngester().run(dry_run=True)
    assert result.chunk_count == 0


def test_dry_run_chunks_accumulate_across_multiple_items() -> None:
    source = StubSource(items=[Item(id="a", payload="x"), Item(id="b", payload="y")])
    result = StubIngester(source=source).run(dry_run=True)
    assert result.dry_run_chunks == 2  # StubChunker returns 1 chunk per item


# ── AC-007: URI-based dedup ────────────────────────────────────────────────────

def test_dedup_pattern_a_fresh_db_processes_all() -> None:
    """Pattern A: no existing URIs → all 3 items processed."""
    items = [
        Item(id="a.pdf", payload="text a"),
        Item(id="b.pdf", payload="text b"),
        Item(id="c.pdf", payload="text c"),
    ]
    sink = StubVectorSink()
    result = StubIngester(source=StubSource(items=items), sink=sink).run()
    assert result.processed_sources == 3
    assert result.skipped_count == 0
    assert len(sink.write_calls) == 3


def test_dedup_pattern_b_skips_existing_uris() -> None:
    """Pattern B: 2 existing URIs + 3 items → 1 processed, 2 skipped, write once."""
    items = [
        Item(id="a.pdf", payload="text a"),
        Item(id="b.pdf", payload="text b"),
        Item(id="c.pdf", payload="text c"),
    ]
    sink = PreloadedSink(_existing={"a.pdf", "b.pdf"})
    result = StubIngester(source=StubSource(items=items), sink=sink).run()
    assert result.processed_sources == 1
    assert result.skipped_count == 2
    assert len(sink.write_calls) == 1
    _, _, written_item, _ = sink.write_calls[0]
    assert written_item.id == "c.pdf"


# ── AC-007b: force bypasses dedup ─────────────────────────────────────────────

def test_force_disables_dedup() -> None:
    """force=True: all items are processed even if URIs exist in the sink."""
    items = [
        Item(id="a.pdf", payload="text a"),
        Item(id="b.pdf", payload="text b"),
        Item(id="c.pdf", payload="text c"),
    ]
    sink = PreloadedSink(_existing={"a.pdf", "b.pdf"})
    result = StubIngester(source=StubSource(items=items), sink=sink).run(force=True)
    assert result.processed_sources == 3
    assert result.skipped_count == 0
    assert len(sink.write_calls) == 3


# ── AC-R-003: idempotency (real SQLiteVecSink) ─────────────────────────────────

@pytest.mark.needs_sqlite_vec
def test_idempotency_same_row_count_on_second_run(tmp_path: Path) -> None:
    """Running the same ingester twice produces the same row count (upsert)."""
    db_path = str(tmp_path / "rag.db")
    items = [
        Item(id="doc1.txt", payload="hello world"),
        Item(id="doc2.txt", payload="foo bar baz"),
    ]
    source = StubSource(items=items)
    sink = SQLiteVecSink(db_path=db_path, dim=3)
    ingester = _make_e2e_ingester(source, sink)

    ingester.run(force=True)
    conn = sqlite3.connect(db_path)
    count_after_first = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()

    ingester.run(force=True)
    conn = sqlite3.connect(db_path)
    count_after_second = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()

    assert count_after_first == count_after_second
    assert count_after_first > 0


@pytest.mark.needs_sqlite_vec
def test_idempotency_no_unique_constraint_error(tmp_path: Path) -> None:
    """Second run must not raise any exception (ON CONFLICT upsert)."""
    db_path = str(tmp_path / "rag.db")
    items = [Item(id="doc.txt", payload="some content")]
    sink = SQLiteVecSink(db_path=db_path, dim=3)
    ingester = _make_e2e_ingester(StubSource(items=items), sink)

    ingester.run(force=True)
    result = ingester.run(force=True)
    assert result.failures == []


# ── AC-001 e2e: real FixedSizeChunker + real SQLiteVecSink ────────────────────

@pytest.mark.needs_sqlite_vec
def test_e2e_run_processes_two_sources(tmp_path: Path) -> None:
    """e2e: 2 items → processed_sources == 2, rows inserted."""
    db_path = str(tmp_path / "rag.db")
    items = [
        Item(id="src1.txt", payload="hello world"),
        Item(id="src2.txt", payload="foo bar baz"),
    ]
    sink = SQLiteVecSink(db_path=db_path, dim=3)
    result = _make_e2e_ingester(StubSource(items=items), sink).run()

    assert result.processed_sources == 2
    assert result.chunk_count > 0
    assert result.failures == []

    conn = sqlite3.connect(db_path)
    row_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    assert row_count == result.chunk_count


@pytest.mark.needs_sqlite_vec
def test_e2e_dedup_with_real_sink(tmp_path: Path) -> None:
    """e2e dedup: second run (without force) skips already-ingested URIs."""
    db_path = str(tmp_path / "rag.db")
    items_first = [
        Item(id="a.txt", payload="hello"),
        Item(id="b.txt", payload="world"),
    ]
    items_second = [
        Item(id="a.txt", payload="hello"),
        Item(id="b.txt", payload="world"),
        Item(id="c.txt", payload="new content"),
    ]
    sink = SQLiteVecSink(db_path=db_path, dim=3)

    first_result = _make_e2e_ingester(StubSource(items=items_first), sink).run()
    assert first_result.processed_sources == 2

    second_result = _make_e2e_ingester(StubSource(items=items_second), sink).run()
    assert second_result.processed_sources == 1
    assert second_result.skipped_count == 2


# ── failure path ───────────────────────────────────────────────────────────────

def test_run_records_failure_on_extractor_exception() -> None:
    class BrokenExtractor(StubExtractor):
        def extract(self, item: Item) -> str:
            raise RuntimeError("extraction failed")

    ingester = StubIngester()
    ingester.extractor = BrokenExtractor()
    result = ingester.run()
    assert len(result.failures) == 1
    assert "extraction failed" in result.failures[0]["error"]
    assert result.failures[0]["source_uri"] == "item-1"


def test_run_continues_after_per_item_failure() -> None:
    """One failing item does not abort remaining items."""
    call_count = 0

    class FlakyExtractor(StubExtractor):
        def extract(self, item: Item) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first item fails")
            return str(item.payload)

    source = StubSource(items=[Item(id="a", payload="x"), Item(id="b", payload="y")])
    sink = StubVectorSink()
    ingester = StubIngester(source=source, sink=sink)
    ingester.extractor = FlakyExtractor()
    result = ingester.run()
    assert len(result.failures) == 1
    assert len(sink.write_calls) == 1  # second item succeeded


# ── ConfigurationError ─────────────────────────────────────────────────────────

def test_missing_required_attr_raises_configuration_error() -> None:
    class IncompleteIngester(Ingester):
        pass  # no attributes set

    with pytest.raises(ConfigurationError):
        IncompleteIngester().run()
