"""AC-013: CompositeSink

実装ファイル: packages/digestkit/src/digestkit/sinks/composite.py
対応 SR: SR-F-010 / SR-R-001
"""

from __future__ import annotations

import pytest

from digestkit.digester import ConfigurationError
from digestkit.sinks import SinkError
from digestkit.sinks.composite import CompositeSink, CompositeSinkError
from digestkit.types import Digest, Item


def _make_digest(**kwargs: object) -> Digest:
    defaults: dict[str, object] = {
        "summary": "test summary",
        "tokens_in": 100,
        "tokens_out": 50,
        "latency_ms": 200,
        "model": "claude-3",
    }
    defaults.update(kwargs)
    return Digest(**defaults)  # type: ignore[arg-type]


def _make_item(item_id: str = "item-001") -> Item:
    return Item(id=item_id, payload=None)


class _RecordingSink:
    """呼び出し順序を記録するテスト用 Fake Sink."""

    def __init__(self, name: str, *, fail: bool = False) -> None:
        self._name = name
        self._fail = fail
        self.calls: list[tuple[Digest, Item]] = []

    def write(self, digest: Digest, item: Item) -> None:
        self.calls.append((digest, item))
        if self._fail:
            raise SinkError(f"{self._name} failed")


def test_composite_sink_calls_all_inner_sinks_in_order() -> None:
    """AC-013: A + B + C の順で write 呼び出し."""
    # Arrange
    call_order: list[str] = []
    digest = _make_digest()
    item = _make_item()

    class _OrderedSink:
        def __init__(self, name: str) -> None:
            self._name = name

        def write(self, digest: Digest, item: Item) -> None:
            call_order.append(self._name)

    sink_a = _OrderedSink("A")
    sink_b = _OrderedSink("B")
    sink_c = _OrderedSink("C")
    composite = CompositeSink([sink_a, sink_b, sink_c])

    # Act
    composite.write(digest, item)

    # Assert
    assert call_order == ["A", "B", "C"]


def test_composite_sink_continues_after_inner_sink_failure() -> None:
    """AC-013: 中央 Sink (B) が失敗しても A と C は呼ばれる."""
    # Arrange
    digest = _make_digest()
    item = _make_item()
    sink_a = _RecordingSink("A")
    sink_b = _RecordingSink("B", fail=True)
    sink_c = _RecordingSink("C")
    composite = CompositeSink([sink_a, sink_b, sink_c])

    # Act
    with pytest.raises(CompositeSinkError):
        composite.write(digest, item)

    # Assert: A と C は呼ばれている
    assert len(sink_a.calls) == 1
    assert len(sink_c.calls) == 1


def test_composite_sink_raises_aggregated_error_when_inner_fails() -> None:
    """AC-013: B の例外が CompositeSinkError として集約送出される."""
    # Arrange
    digest = _make_digest()
    item = _make_item()
    composite = CompositeSink(
        [
            _RecordingSink("A"),
            _RecordingSink("B", fail=True),
            _RecordingSink("C"),
        ]
    )

    # Act / Assert
    with pytest.raises(CompositeSinkError):
        composite.write(digest, item)


def test_composite_sink_aggregated_error_contains_inner_exception() -> None:
    """AC-013: CompositeSinkError に B のエラー情報が含まれる."""
    # Arrange
    digest = _make_digest()
    item = _make_item()
    composite = CompositeSink(
        [
            _RecordingSink("A"),
            _RecordingSink("B", fail=True),
            _RecordingSink("C"),
        ]
    )

    # Act
    with pytest.raises(CompositeSinkError) as exc_info:
        composite.write(digest, item)

    # Assert
    err = exc_info.value
    assert len(err.errors) == 1
    assert "B failed" in str(err.errors[0])


def test_composite_sink_aggregates_multiple_failures() -> None:
    """A と C が両方失敗したとき errors に 2 件含まれる."""
    # Arrange
    digest = _make_digest()
    item = _make_item()
    composite = CompositeSink(
        [
            _RecordingSink("A", fail=True),
            _RecordingSink("B"),
            _RecordingSink("C", fail=True),
        ]
    )

    # Act
    with pytest.raises(CompositeSinkError) as exc_info:
        composite.write(digest, item)

    # Assert
    assert len(exc_info.value.errors) == 2


def test_composite_sink_no_error_when_all_succeed() -> None:
    """全 Sink が成功したとき例外は送出されない."""
    # Arrange
    digest = _make_digest()
    item = _make_item()
    composite = CompositeSink(
        [
            _RecordingSink("A"),
            _RecordingSink("B"),
        ]
    )

    # Act / Assert (例外なし)
    composite.write(digest, item)


def test_composite_sink_raises_configuration_error_for_empty_list() -> None:
    """空の sinks リストで ConfigurationError."""
    # Act / Assert
    with pytest.raises(ConfigurationError):
        CompositeSink([])


def test_composite_sink_add_extends_sink_list() -> None:
    """CompositeSink.__add__ で新たな CompositeSink が返される."""
    # Arrange
    call_order: list[str] = []
    digest = _make_digest()
    item = _make_item()

    class _NamedSink:
        def __init__(self, name: str) -> None:
            self._name = name

        def write(self, digest: Digest, item: Item) -> None:
            call_order.append(self._name)

    base = CompositeSink([_NamedSink("A"), _NamedSink("B")])
    extended = base + _NamedSink("C")

    # Act
    extended.write(digest, item)

    # Assert
    assert call_order == ["A", "B", "C"]
    assert isinstance(extended, CompositeSink)


def test_composite_sink_is_sink_error_subclass() -> None:
    """CompositeSinkError は SinkError のサブクラス."""
    assert issubclass(CompositeSinkError, SinkError)
