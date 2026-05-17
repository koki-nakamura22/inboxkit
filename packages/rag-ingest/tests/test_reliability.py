"""Reliability tests: AC-R-001 (Source-level embed failure handling)."""

from __future__ import annotations

from typing import Any

from conftest import StubChunker, StubExtractor, StubSource, StubVectorSink
from rag_ingest._upstream import Item
from rag_ingest.exceptions import EmbeddingError
from rag_ingest.ingester import Ingester, RunResult
from rag_ingest.types import Chunk, Vector


class _FailingEmbedder:
    provider: str = "stub"
    model: str = "stub-fail"

    def embed(self, chunks: list[Chunk]) -> list[Vector]:
        raise EmbeddingError("simulated embed failure")

    def dim(self) -> int:
        return 4


def _make_ingester(source: Any, embedder: Any = None, sink: Any = None) -> Ingester:
    class _Ingester(Ingester):
        pass

    ing = _Ingester()
    ing.source = source
    ing.extractor = StubExtractor()
    ing.chunker = StubChunker()
    ing.embedder = embedder or _FailingEmbedder()
    ing.sink = sink or StubVectorSink()
    return ing


# ── AC-R-001: embed failure → Source-level skip, run() continues ──────────────


def test_embed_failure_records_one_failure_for_single_source() -> None:
    source = StubSource(items=[Item(id="doc-1", payload="hello")])
    result = _make_ingester(source).run()

    assert len(result.failures) == 1


def test_embed_failure_records_correct_source_uri() -> None:
    source = StubSource(items=[Item(id="doc-1", payload="hello")])
    result = _make_ingester(source).run()

    assert result.failures[0]["source_uri"] == "doc-1"


def test_embed_failure_records_error_message() -> None:
    source = StubSource(items=[Item(id="doc-1", payload="hello")])
    result = _make_ingester(source).run()

    assert "simulated" in result.failures[0]["error"]


def test_embed_failure_run_returns_run_result_without_raising() -> None:
    source = StubSource(items=[Item(id="doc-1", payload="text")])
    result = _make_ingester(source).run()

    assert isinstance(result, RunResult)


def test_embed_failure_processed_sources_zero_when_single_source_fails() -> None:
    source = StubSource(items=[Item(id="doc-1", payload="hello")])
    result = _make_ingester(source).run()

    assert result.processed_sources == 0


def test_embed_failure_middle_source_other_two_sources_written() -> None:
    call_count = 0

    class _SelectiveEmbedder:
        provider: str = "stub"
        model: str = "stub-selective"

        def embed(self, chunks: list[Chunk]) -> list[Vector]:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise EmbeddingError("second source fails")
            return [[0.1, 0.2, 0.3] for _ in chunks]

        def dim(self) -> int:
            return 3

    items = [
        Item(id="a", payload="first"),
        Item(id="b", payload="second"),
        Item(id="c", payload="third"),
    ]
    sink = StubVectorSink()
    result = _make_ingester(StubSource(items=items), embedder=_SelectiveEmbedder(), sink=sink).run()

    assert len(result.failures) == 1
    assert result.failures[0]["source_uri"] == "b"
    assert result.processed_sources == 2
    assert len(sink.write_calls) == 2


def test_embed_failure_all_five_sources_fail_run_completes() -> None:
    items = [Item(id=f"doc-{i}", payload=f"text {i}") for i in range(5)]
    sink = StubVectorSink()
    result = _make_ingester(StubSource(items=items), sink=sink).run()

    assert len(result.failures) == 5
    assert result.processed_sources == 0
    assert len(sink.write_calls) == 0


def test_embed_failure_first_source_fails_remaining_two_succeed() -> None:
    call_count = 0

    class _FirstFailEmbedder:
        provider: str = "stub"
        model: str = "stub-first-fail"

        def embed(self, chunks: list[Chunk]) -> list[Vector]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise EmbeddingError("first fails")
            return [[0.1, 0.2, 0.3] for _ in chunks]

        def dim(self) -> int:
            return 3

    items = [
        Item(id="first", payload="fail"),
        Item(id="second", payload="ok"),
        Item(id="third", payload="ok"),
    ]
    sink = StubVectorSink()
    result = _make_ingester(StubSource(items=items), embedder=_FirstFailEmbedder(), sink=sink).run()

    assert len(result.failures) == 1
    assert result.failures[0]["source_uri"] == "first"
    assert result.processed_sources == 2
    assert len(sink.write_calls) == 2
