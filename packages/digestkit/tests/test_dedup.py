"""AC-014: Digester-level dedup (D-001)

実装ファイル: packages/digestkit/src/digestkit/dedup.py (or 同等)
対応 SR: SR-F-011
decision-defaults.md D-001: Digester がオプショナル属性 seen_store: SeenStore | None を持つ
                            default は SQLiteSeenStore("~/.cache/digestkit/<class>.db")
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from digestkit.dedup import SQLiteSeenStore, default_seen_store_path
from digestkit.digester import Digester
from digestkit.types import Digest, Item


def _make_digest(**kwargs: object) -> Digest:
    defaults: dict[str, object] = {
        "summary": "test summary",
        "tokens_in": 10,
        "tokens_out": 5,
        "latency_ms": 100,
        "model": "claude-3",
    }
    defaults.update(kwargs)
    return Digest(**defaults)  # type: ignore[arg-type]


def _make_item(item_id: str = "item-001") -> Item:
    return Item(id=item_id, payload=None)


class _FakeSource:
    def __init__(self, items: list[Item]) -> None:
        self._items = items

    def fetch(self) -> Iterable[Item]:
        return list(self._items)


class _FakeExtractor:
    def extract(self, item: Item) -> str:
        return f"text for {item.id}"


class _FakeSummarizer:
    def summarize(self, text: str, item: Item) -> Digest:
        return _make_digest()


class _FakeSink:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[tuple[Digest, Item]] = []

    def write(self, digest: Digest, item: Item) -> None:
        self.calls.append((digest, item))
        if self._fail:
            raise RuntimeError("write failed")


def test_seen_store_skips_item_on_second_run(tmp_path: Path) -> None:
    """AC-014: 同一 Item.id で run() を 2 回. 2 回目で skip され RunResult.skipped == 1."""
    # Arrange
    item = _make_item("item-001")
    store = SQLiteSeenStore(tmp_path / "seen.db")

    class _D(Digester):
        source = _FakeSource([item])
        extractor = _FakeExtractor()
        summarizer = _FakeSummarizer()
        sink = _FakeSink()

    d = _D(seen_store=store)

    # Act
    result1 = d.run()
    result2 = d.run()

    # Assert
    assert result1.success == 1
    assert result1.skipped == 0
    assert result2.success == 0
    assert result2.skipped == 1


def test_seen_store_records_id_only_after_successful_write(tmp_path: Path) -> None:
    """D-001: write 失敗時は seen_store に id を追加しない (次回 run で再試行可能)."""
    # Arrange
    item = _make_item("item-001")
    store = SQLiteSeenStore(tmp_path / "seen.db")
    failing_sink = _FakeSink(fail=True)

    class _D(Digester):
        source = _FakeSource([item])
        extractor = _FakeExtractor()
        summarizer = _FakeSummarizer()
        sink = failing_sink

    d = _D(seen_store=store)

    # Act: first run — write fails
    result1 = d.run()

    # Assert: item not added to seen_store after failed write
    assert len(result1.failures) == 1
    assert result1.failures[0].stage == "write"
    assert not store.has("item-001")

    # Act: second run — item must be retried, not skipped
    result2 = d.run()

    # Assert: item was retried (skipped count is 0)
    assert result2.skipped == 0
    assert len(result2.failures) == 1


def test_seen_store_disabled_when_seen_store_is_none() -> None:
    """D-001: Digester(seen_store=None) で重複防止が無効化される."""
    # Arrange
    item = _make_item("item-001")
    recording_sink = _FakeSink()

    class _D(Digester):
        source = _FakeSource([item])
        extractor = _FakeExtractor()
        summarizer = _FakeSummarizer()
        sink = recording_sink

    d = _D(seen_store=None)

    # Act: run twice with the same item
    result1 = d.run()
    result2 = d.run()

    # Assert: both runs process the item (no dedup)
    assert result1.success == 1
    assert result1.skipped == 0
    assert result2.success == 1
    assert result2.skipped == 0
    assert len(recording_sink.calls) == 2


def test_default_seen_store_uses_xdg_cache_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-001: デフォルト seen_store の path が XDG_CACHE_HOME or ~/.cache/digestkit/<class>.db."""
    # Arrange: redirect XDG_CACHE_HOME to tmp_path so no real ~/.cache is touched
    xdg_cache = tmp_path / "xdg_cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))

    class _MyDigester(Digester):
        source = _FakeSource([])
        extractor = _FakeExtractor()
        summarizer = _FakeSummarizer()
        sink = _FakeSink()

    # Act: instantiate without explicit seen_store
    d = _MyDigester()

    # Assert: default seen_store is SQLiteSeenStore under XDG_CACHE_HOME/digestkit/<class>.db
    assert isinstance(d.seen_store, SQLiteSeenStore)
    expected = xdg_cache / "digestkit" / "_MyDigester.db"
    assert (xdg_cache / "digestkit" / "_MyDigester.db").exists(), (
        f"expected SQLite DB at {expected}"
    )
