"""Issue #12: SeenStore の dedup キーをコンテンツハッシュ等に切り替え可能にする.

採用方針 (案 B 派生): ``Digester.dedup_key`` (Callable[[Item], str]) で
キー戦略を差し替える. ``SeenStore`` Protocol は変更せず、Item.id 意味論も
保ったまま、内容ベース dedup を可能にする.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

import pytest

from digestkit import content_sha256_key, item_id_key
from digestkit.dedup import SQLiteSeenStore
from digestkit.digester import Digester
from digestkit.types import Digest, Item

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _make_digest() -> Digest:
    return Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=0, model="stub")


class _FakeSource:
    def __init__(self, items: list[Item]) -> None:
        self._items = items

    def fetch(self) -> Iterable[Item]:
        return iter(self._items)


class _FakeExtractor:
    def extract(self, item: Item) -> str:
        return f"text:{item.id}"


class _FakeSummarizer:
    def summarize(self, text: str, item: Item) -> Digest:
        return _make_digest()


class _RecordingSink:
    def __init__(self) -> None:
        self.calls: list[Item] = []

    def write(self, digest: Digest, item: Item) -> None:
        self.calls.append(item)


# ---------------------------------------------------------------------------
# item_id_key (default strategy)
# ---------------------------------------------------------------------------


def test_item_id_key_returns_item_id() -> None:
    """既定戦略 ``item_id_key`` は ``Item.id`` を返す (後方互換 baseline)."""
    item = Item(id="abc", payload=None)
    assert item_id_key(item) == "abc"


# ---------------------------------------------------------------------------
# content_sha256_key (built-in helper)
# ---------------------------------------------------------------------------


def test_content_sha256_key_hashes_file_contents(tmp_path: Path) -> None:
    """``content_sha256_key`` は ``Item.payload`` (Path) の SHA-256 を ``sha256:<hex>`` で返す."""
    f = tmp_path / "x.bin"
    data = b"hello world\n" * 1024
    f.write_bytes(data)

    expected = "sha256:" + hashlib.sha256(data).hexdigest()
    assert content_sha256_key(Item(id=str(f), payload=f)) == expected


def test_content_sha256_key_same_content_different_path_yields_same_key(tmp_path: Path) -> None:
    """同一内容の別ファイルは同じキーになる (dedup される)."""
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"same content")
    b.write_bytes(b"same content")

    assert content_sha256_key(Item(id=str(a), payload=a)) == content_sha256_key(
        Item(id=str(b), payload=b)
    )


def test_content_sha256_key_changed_content_yields_different_key(tmp_path: Path) -> None:
    """同一パスでも内容が変われば別キーになる (再要約が走る)."""
    f = tmp_path / "x.bin"
    f.write_bytes(b"v1")
    k1 = content_sha256_key(Item(id=str(f), payload=f))

    f.write_bytes(b"v2")
    k2 = content_sha256_key(Item(id=str(f), payload=f))

    assert k1 != k2


def test_content_sha256_key_rejects_non_path_payload() -> None:
    """payload が Path でない時は TypeError (誤用を早期発見)."""
    with pytest.raises(TypeError):
        content_sha256_key(Item(id="x", payload="not a path"))


# ---------------------------------------------------------------------------
# Digester.dedup_key integration
# ---------------------------------------------------------------------------


def _make_digester(
    items: list[Item],
    *,
    seen_store: object,
    dedup_key: object = None,
) -> tuple[Digester, _RecordingSink]:
    sink = _RecordingSink()

    class _D(Digester):
        source = _FakeSource(items)
        extractor = _FakeExtractor()
        summarizer = _FakeSummarizer()

    _D.sink = sink  # type: ignore[assignment]

    kwargs: dict[str, object] = {"seen_store": seen_store}
    if dedup_key is not None:
        kwargs["dedup_key"] = dedup_key
    return _D(**kwargs), sink  # type: ignore[arg-type]


def test_default_dedup_key_uses_item_id(tmp_path: Path) -> None:
    """``dedup_key`` 未指定なら ``Item.id`` で dedup される (後方互換)."""
    item = Item(id="dup", payload=None)
    store = SQLiteSeenStore(tmp_path / "seen.db")

    d, _ = _make_digester([item], seen_store=store)
    d.run()
    result2 = d.run()

    assert result2.skipped == 1
    assert store.has("dup")


def test_content_hash_dedup_skips_same_content_at_different_paths(tmp_path: Path) -> None:
    """``dedup_key=content_sha256_key`` で同一内容の別パスファイルが skip される (Issue #12)."""
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"same content")
    b.write_bytes(b"same content")
    items = [Item(id=str(a), payload=a), Item(id=str(b), payload=b)]
    store = SQLiteSeenStore(tmp_path / "seen.db")

    d, sink = _make_digester(items, seen_store=store, dedup_key=content_sha256_key)
    result = d.run()

    # 1 件目が write、2 件目は内容ハッシュ一致で skip
    assert result.success == 1
    assert result.skipped == 1
    assert len(sink.calls) == 1


def test_content_hash_dedup_reprocesses_when_content_changes(tmp_path: Path) -> None:
    """``dedup_key=content_sha256_key`` で同一パスでも内容差し替え時に再要約される."""
    f = tmp_path / "x.txt"
    f.write_bytes(b"v1")
    item_v1 = Item(id=str(f), payload=f)
    store = SQLiteSeenStore(tmp_path / "seen.db")

    # v1 を 1 度処理
    d, sink = _make_digester([item_v1], seen_store=store, dedup_key=content_sha256_key)
    d.run()
    assert len(sink.calls) == 1

    # 内容を v2 に差し替えて再 run
    f.write_bytes(b"v2")
    item_v2 = Item(id=str(f), payload=f)
    d2, sink2 = _make_digester([item_v2], seen_store=store, dedup_key=content_sha256_key)
    result = d2.run()

    # path 同一でも内容ハッシュが違うので再処理される
    assert result.success == 1
    assert result.skipped == 0
    assert len(sink2.calls) == 1


def test_dedup_key_override_via_class_attribute(tmp_path: Path) -> None:
    """サブクラス class attr で dedup_key を差し替えられる (constructor 引数と同等)."""
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    items = [Item(id=str(a), payload=a), Item(id=str(b), payload=b)]
    store = SQLiteSeenStore(tmp_path / "seen.db")
    sink = _RecordingSink()

    class _D(Digester):
        source = _FakeSource(items)
        extractor = _FakeExtractor()
        summarizer = _FakeSummarizer()
        dedup_key = staticmethod(content_sha256_key)

    _D.sink = sink  # type: ignore[assignment]
    d = _D(seen_store=store)
    result = d.run()

    assert result.success == 1
    assert result.skipped == 1


def test_dedup_key_failure_recorded_as_failure_and_continues(tmp_path: Path) -> None:
    """``dedup_key`` 関数の例外は当該 Item のみを失敗扱いにし、後続は処理継続する."""
    good = tmp_path / "good.txt"
    good.write_bytes(b"ok")
    items = [
        Item(id="bad", payload=None),  # content_sha256_key は TypeError を投げる
        Item(id=str(good), payload=good),
    ]
    store = SQLiteSeenStore(tmp_path / "seen.db")

    d, sink = _make_digester(items, seen_store=store, dedup_key=content_sha256_key)
    result = d.run()

    assert result.success == 1
    assert len(result.failures) == 1
    assert result.failures[0].item.id == "bad"
    assert isinstance(result.failures[0].error, TypeError)
    assert len(sink.calls) == 1


def test_dedup_key_not_called_when_seen_store_is_none(tmp_path: Path) -> None:
    """``seen_store=None`` 時は dedup_key は呼ばれない (TypeError 等で死なない)."""
    items = [Item(id="x", payload=None)]  # content_sha256_key を呼べば TypeError

    d, sink = _make_digester(items, seen_store=None, dedup_key=content_sha256_key)
    result = d.run()

    assert result.success == 1
    assert result.failures == []
    assert len(sink.calls) == 1


def test_dedup_key_not_called_in_dry_run(tmp_path: Path) -> None:
    """dry_run=True 時は dedup_key も SeenStore も使わない (既存挙動を保つ)."""
    items = [Item(id="x", payload=None)]
    store = SQLiteSeenStore(tmp_path / "seen.db")

    d, _ = _make_digester(items, seen_store=store, dedup_key=content_sha256_key)
    result = d.run(dry_run=True)

    # dry_run なので skip カウント (= dedup スキップではなく dry_run スキップ)
    assert result.skipped == 1
    assert result.success == 0
    assert not store.has("x")
