"""AC-002: 4 Protocol の構造的型適合 (`isinstance` チェック)

実装ファイル: packages/digestkit/src/digestkit/protocols.py
対応 SR: SR-F-002
"""

from __future__ import annotations

from collections.abc import Iterable

from digestkit.protocols import Extractor, Sink, Source, Summarizer
from digestkit.types import Digest, Item


def test_source_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Source Protocol が duck-typed クラスを isinstance で True と判定."""

    # Arrange
    class FakeSource:
        def fetch(self) -> Iterable[Item]:
            return []

    obj = FakeSource()
    # Act / Assert
    assert isinstance(obj, Source)


def test_extractor_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Extractor Protocol が duck-typed クラスを isinstance で True と判定."""

    # Arrange
    class FakeExtractor:
        def extract(self, item: Item) -> str:
            return ""

    obj = FakeExtractor()
    # Act / Assert
    assert isinstance(obj, Extractor)


def test_summarizer_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Summarizer Protocol が duck-typed クラスを isinstance で True と判定."""

    # Arrange
    class FakeSummarizer:
        def summarize(self, text: str, item: Item) -> Digest:
            return Digest(summary="", tokens_in=0, tokens_out=0, latency_ms=0, model="")

    obj = FakeSummarizer()
    # Act / Assert
    assert isinstance(obj, Summarizer)


def test_sink_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Sink Protocol が duck-typed クラスを isinstance で True と判定."""

    # Arrange
    class FakeSink:
        def write(self, digest: Digest, item: Item) -> None:
            pass

    obj = FakeSink()
    # Act / Assert
    assert isinstance(obj, Sink)


def test_protocol_isinstance_returns_false_when_method_is_missing() -> None:
    """AC-002: 必須メソッドを欠くクラスは isinstance で False."""

    # Arrange
    class Empty:
        pass

    obj = Empty()
    # Act / Assert
    assert not isinstance(obj, Source)
    assert not isinstance(obj, Extractor)
    assert not isinstance(obj, Summarizer)
    assert not isinstance(obj, Sink)
