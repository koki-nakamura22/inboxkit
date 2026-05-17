"""AC-P-001 / AC-P-002: Performance

実装ファイル: 横断 (Digester / Source / Sink すべて)
対応 SR: SR-P-002 / SR-P-003
"""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Iterable

import pytest

from digestkit.digester import Digester
from digestkit.types import Digest, Item

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _make_items(n: int) -> list[Item]:
    return [Item(id=str(i), payload=None) for i in range(n)]


def _stub_digest(item: Item) -> Digest:
    return Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=0, model="stub")


class _StubSource:
    def __init__(self, items: list[Item]) -> None:
        self._items = items

    def fetch(self) -> Iterable[Item]:
        return iter(self._items)


class _StubExtractor:
    def extract(self, item: Item) -> str:
        return "text"


class _StubSummarizer:
    def summarize(self, text: str, item: Item) -> Digest:
        return _stub_digest(item)


class _StubSink:
    def write(self, digest: Digest, item: Item) -> None:
        pass


def _make_digester(n: int) -> Digester:
    _src = _StubSource(_make_items(n))
    _ext = _StubExtractor()
    _sum = _StubSummarizer()
    _snk = _StubSink()

    class _PerfDigester(Digester):
        source = _src  # type: ignore[assignment]
        extractor = _ext  # type: ignore[assignment]
        summarizer = _sum  # type: ignore[assignment]
        sink = _snk  # type: ignore[assignment]

    return _PerfDigester(seen_store=None)


# ---------------------------------------------------------------------------
# AC-P-001: フレームワーク純オーバーヘッド 1 件 ≤ 100ms
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_framework_overhead_per_item_under_100ms() -> None:
    """AC-P-001: LLM mock + 10 件で 1 件あたり ≤ 100ms."""
    # Arrange
    digester = _make_digester(10)

    # Act
    start = time.perf_counter()
    result = digester.run()
    elapsed = time.perf_counter() - start

    # Assert
    assert result.success == 10
    assert elapsed / 10 < 0.1, f"per-item overhead = {elapsed / 10:.3f}s, target ≤ 0.1s"


# ---------------------------------------------------------------------------
# AC-P-002: 1,000 件完走 / メモリ ≤ 200MB / 所要時間 ≤ 100 秒
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_run_completes_for_1000_items_under_memory_limit() -> None:
    """AC-P-002: 1,000 件処理. エラーなし完走 / メモリ ≤ 200MB / 所要時間 ≤ 100 秒."""
    # Arrange
    digester = _make_digester(1000)

    # Act
    tracemalloc.start()
    start = time.perf_counter()
    result = digester.run()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - start

    # Assert
    assert result.success == 1000
    assert peak < 200 * 1024 * 1024, f"peak memory = {peak / 1024 / 1024:.1f}MB"
    assert elapsed < 100, f"elapsed = {elapsed:.1f}s"
