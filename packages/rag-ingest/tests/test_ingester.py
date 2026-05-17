"""AC-001 / AC-001c: Ingester.run() skeleton — normal flow and dry_run mode."""
from __future__ import annotations

import pytest

from conftest import StubChunker, StubEmbedder, StubExtractor, StubSource, StubVectorSink

from rag_ingest._upstream import Item
from rag_ingest.exceptions import ConfigurationError
from rag_ingest.ingester import Ingester, RunResult


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


# ── AC-001c: dry_run mode ──────────────────────────────────────────────────────

def test_dry_run_chunks_recorded() -> None:
    result = StubIngester().run(dry_run=True)
    assert result.dry_run_chunks == 1


def test_dry_run_processed_sources_incremented() -> None:
    result = StubIngester().run(dry_run=True)
    assert result.processed_sources == 1


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


def test_run_ingest_context_carries_embedder_metadata() -> None:
    sink = StubVectorSink()
    StubIngester(sink=sink).run()
    _, _, _, ctx = sink.write_calls[0]
    assert ctx.embedder_provider == "stub"
    assert ctx.embedder_model == "stub-model"
    assert ctx.chunker_config == {"chunk_size": 512, "overlap": 0, "unit": "tokens"}


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
