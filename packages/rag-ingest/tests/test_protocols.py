"""AC-002: duck-typed implementations pass isinstance checks for all Protocols."""
from __future__ import annotations

from conftest import StubChunker, StubEmbedder, StubVectorSink

from rag_ingest.protocols import Chunker, Embedder, VectorSink


def test_chunker_isinstance() -> None:
    assert isinstance(StubChunker(), Chunker)


def test_embedder_isinstance() -> None:
    assert isinstance(StubEmbedder(), Embedder)


def test_vector_sink_isinstance() -> None:
    assert isinstance(StubVectorSink(), VectorSink)


def test_chunker_non_subtype_fails() -> None:
    class NoChunk:
        pass

    assert not isinstance(NoChunk(), Chunker)


def test_embedder_non_subtype_fails() -> None:
    class NoEmbed:
        pass

    assert not isinstance(NoEmbed(), Embedder)


def test_vector_sink_non_subtype_fails() -> None:
    class NoWrite:
        pass

    assert not isinstance(NoWrite(), VectorSink)
