"""AC-001 / AC-001b / AC-001c / AC-R-001: Digester ABC の振る舞い

実装ファイル: packages/digestkit/src/digestkit/digester.py
対応 SR: SR-F-001 / SR-R-001
"""

from __future__ import annotations

from typing import Iterable

import pytest

from digestkit.digester import ConfigurationError, Digester, DigestkitError, RunResult
from digestkit.types import Digest, Item


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _make_items(n: int) -> list[Item]:
    return [Item(id=str(i), payload=None) for i in range(n)]


def _stub_digest(item: Item) -> Digest:
    return Digest(
        summary=f"summary:{item.id}",
        tokens_in=1,
        tokens_out=1,
        latency_ms=0,
        model="stub",
    )


class _StubSource:
    def __init__(self, items: list[Item]) -> None:
        self._items = items

    def fetch(self) -> Iterable[Item]:
        return iter(self._items)


class _SpyExtractor:
    """Records calls; raises RuntimeError for IDs in fail_on."""

    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.calls: list[Item] = []
        self._fail_on = fail_on or set()

    def extract(self, item: Item) -> str:
        self.calls.append(item)
        if item.id in self._fail_on:
            raise RuntimeError(f"extraction failed: {item.id}")
        return f"text:{item.id}"


class _SpySummarizer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Item]] = []

    def summarize(self, text: str, item: Item) -> Digest:
        self.calls.append((text, item))
        return _stub_digest(item)


class _SpySink:
    def __init__(self) -> None:
        self.calls: list[tuple[Digest, Item]] = []

    def write(self, digest: Digest, item: Item) -> None:
        self.calls.append((digest, item))


def _make_digester(
    items: list[Item],
    fail_on: set[str] | None = None,
) -> tuple[Digester, _SpyExtractor, _SpySummarizer, _SpySink]:
    # Use underscore-prefixed locals to avoid name clash with class attribute names
    # (Python class bodies don't form closures over enclosing function locals)
    _ext = _SpyExtractor(fail_on=fail_on)
    _sum = _SpySummarizer()
    _snk = _SpySink()

    class _ConcreteDigester(Digester):
        source = _StubSource(items)
        extractor = _ext  # type: ignore[assignment]
        summarizer = _sum  # type: ignore[assignment]
        sink = _snk  # type: ignore[assignment]

    d = _ConcreteDigester()
    return d, _ext, _sum, _snk


# ---------------------------------------------------------------------------
# AC-001: 順次実行 + RunResult カウント
# ---------------------------------------------------------------------------


def test_digester_run_processes_all_items_in_order() -> None:
    """AC-001: Source.fetch -> Extractor.extract -> Summarizer.summarize -> Sink.write が順次実行され、3 件の Item で Sink.write が 3 回呼ばれる."""
    # Arrange
    items = _make_items(3)
    d, extractor, summarizer, sink = _make_digester(items)

    # Act
    d.run()

    # Assert — 各コンポーネントが全 3 件を処理
    assert [c.id for c in extractor.calls] == ["0", "1", "2"]
    assert [c[1].id for c in summarizer.calls] == ["0", "1", "2"]
    assert [c[1].id for c in sink.calls] == ["0", "1", "2"]


def test_digester_run_returns_runresult_with_correct_counts() -> None:
    """AC-001: RunResult.success == 3 / failures == 0 / skipped == 0 が返る."""
    # Arrange
    items = _make_items(3)
    d, _, _, _ = _make_digester(items)

    # Act
    result = d.run()

    # Assert
    assert result.success == 3
    assert result.skipped == 0
    assert result.failures == []


# ---------------------------------------------------------------------------
# AC-001b: limit 引数の境界値
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("limit", "expected_processed"),
    [
        (0, 0),
        (1, 1),
        (3, 3),
        (5, 5),
        (6, 5),   # Source が 5 件しか返さないので min(limit, 5)
        (None, 5),
    ],
)
def test_digester_run_respects_limit_argument(limit: int | None, expected_processed: int) -> None:
    """AC-001b: limit 引数の境界値. Source 5 件返す状況で limit=N → 処理件数 == min(N, 5)."""
    # Arrange
    items = _make_items(5)
    d, _, _, sink = _make_digester(items)

    # Act
    result = d.run(limit=limit)

    # Assert
    assert len(sink.calls) == expected_processed
    assert result.success == expected_processed


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------


def test_digester_run_dry_run_skips_sink_write() -> None:
    """AC-011f 関連: dry_run=True で Sink.write が呼ばれず、RunResult.skipped == 件数."""
    # Arrange
    items = _make_items(3)
    d, extractor, summarizer, sink = _make_digester(items)

    # Act
    result = d.run(dry_run=True)

    # Assert
    assert sink.calls == []
    assert result.skipped == 3
    assert result.success == 0
    # extract / summarize は呼ばれている
    assert len(extractor.calls) == 3
    assert len(summarizer.calls) == 3


# ---------------------------------------------------------------------------
# AC-001c: 必須属性欠落で ConfigurationError
# ---------------------------------------------------------------------------


def test_digester_subclass_missing_source_raises_at_instantiation() -> None:
    """AC-001c: source 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    # Arrange
    class _NoSource(Digester):
        extractor = _SpyExtractor()
        summarizer = _SpySummarizer()
        sink = _SpySink()

    # Act / Assert
    with pytest.raises(ConfigurationError):
        _NoSource()


def test_digester_subclass_missing_extractor_raises_at_instantiation() -> None:
    """AC-001c: extractor 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    # Arrange
    class _NoExtractor(Digester):
        source = _StubSource([])
        summarizer = _SpySummarizer()
        sink = _SpySink()

    # Act / Assert
    with pytest.raises(ConfigurationError):
        _NoExtractor()


def test_digester_subclass_missing_summarizer_raises_at_instantiation() -> None:
    """AC-001c: summarizer 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    # Arrange
    class _NoSummarizer(Digester):
        source = _StubSource([])
        extractor = _SpyExtractor()
        sink = _SpySink()

    # Act / Assert
    with pytest.raises(ConfigurationError):
        _NoSummarizer()


def test_digester_subclass_missing_sink_raises_at_instantiation() -> None:
    """AC-001c: sink 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    # Arrange
    class _NoSink(Digester):
        source = _StubSource([])
        extractor = _SpyExtractor()
        summarizer = _SpySummarizer()

    # Act / Assert
    with pytest.raises(ConfigurationError):
        _NoSink()


def test_digester_subclass_missing_all_raises_with_clear_message() -> None:
    """AC-001c: 全属性欠落時、例外メッセージに欠けている属性名すべてが含まれる."""
    # Arrange
    class _EmptyDigester(Digester):
        pass

    # Act / Assert
    with pytest.raises(ConfigurationError, match="source") as exc_info:
        _EmptyDigester()
    msg = str(exc_info.value)
    for attr in ("source", "extractor", "summarizer", "sink"):
        assert attr in msg


# ---------------------------------------------------------------------------
# AC-R-001: 1 件失敗でも継続 (resilience)
# ---------------------------------------------------------------------------


def test_digester_run_continues_after_single_item_extraction_failure() -> None:
    """AC-R-001: 5 件中 3 件目の Extractor が例外を投げても残りを処理. RunResult.success==4 / failures==1."""
    # Arrange — item id "2" (3 件目, 0-indexed) が extract 時に失敗
    items = _make_items(5)
    d, _, _, _ = _make_digester(items, fail_on={"2"})

    # Act
    result = d.run()

    # Assert
    assert result.success == 4
    assert len(result.failures) == 1
    assert result.skipped == 0


def test_digester_run_failure_list_contains_failing_item() -> None:
    """AC-R-001: failures リストに失敗 Item の参照が含まれ、Sink.write は失敗 Item に対しては呼ばれない."""
    # Arrange
    items = _make_items(5)
    d, _, _, sink = _make_digester(items, fail_on={"2"})

    # Act
    result = d.run()

    # Assert — failures[0] は item "2"
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.item.id == "2"
    assert failure.stage == "extract"

    # Sink.write は "2" を除く 4 件のみ
    written_ids = {c[1].id for c in sink.calls}
    assert "2" not in written_ids
    assert len(sink.calls) == 4


# ---------------------------------------------------------------------------
# 例外階層
# ---------------------------------------------------------------------------


def test_configuration_error_is_digestkit_error() -> None:
    """ConfigurationError は DigestkitError のサブクラスである."""
    assert issubclass(ConfigurationError, DigestkitError)


def test_digestkit_error_is_exception() -> None:
    """DigestkitError は Exception のサブクラスである."""
    assert issubclass(DigestkitError, Exception)
