from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from digestkit.types import DigestkitError, Item


class DedupStoreError(DigestkitError):
    """重複防止ストアの失敗."""


@runtime_checkable
class SeenStore(Protocol):
    def has(self, item_id: str) -> bool: ...
    def add(self, item_id: str) -> None: ...


def _default_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) if xdg else Path.home() / ".cache"


def default_seen_store_path(class_name: str) -> Path:
    return _default_cache_dir() / "digestkit" / f"{class_name}.db"


class SQLiteSeenStore:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_items (item_id TEXT PRIMARY KEY, added_at TEXT)"
        )
        self._conn.commit()

    def has(self, item_id: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM seen_items WHERE item_id = ?", (item_id,))
        return cur.fetchone() is not None

    def add(self, item_id: str) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT OR IGNORE INTO seen_items VALUES (?, ?)",
                    (item_id, datetime.now(UTC).isoformat()),
                )
        except sqlite3.Error as e:
            raise DedupStoreError(str(e)) from e


# ---------------------------------------------------------------------------
# Built-in dedup key strategies (Issue #12)
# ---------------------------------------------------------------------------

# 既定の chunk size (8 MiB). 大きめのファイルでもメモリに乗せきらず、
# 小さめなら 1 read で済む実用値.
_HASH_CHUNK_BYTES = 8 * 1024 * 1024


def item_id_key(item: Item) -> str:
    """既定の dedup キー戦略: ``Item.id`` をそのまま使う.

    ``Digester.dedup_key`` 未指定時の挙動と等価. 明示する用途や、
    別の戦略と切り替える wrapper を書く時の baseline として公開する.
    """
    return item.id


def content_sha256_key(item: Item) -> str:
    """``Item.payload`` (``pathlib.Path``) の SHA-256 を dedup キーとして返す.

    `LocalDirectorySource` のように payload が ``Path`` のソース向け. 同一内容
    のファイルは絶対パスが違っても同じキーになり、内容差し替え時はキーが変わって
    再要約が走る. Issue #12 のユースケース解決のためのヘルパ.

    Raises:
        TypeError: payload が ``Path`` でない時.
    """
    payload = item.payload
    if not isinstance(payload, Path):
        raise TypeError(
            f"content_sha256_key requires Item.payload to be a pathlib.Path, "
            f"got {type(payload).__name__}"
        )
    h = hashlib.sha256()
    with payload.open("rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_BYTES), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"
