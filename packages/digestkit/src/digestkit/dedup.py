from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from digestkit.types import DigestkitError


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
            "CREATE TABLE IF NOT EXISTS seen_items "
            "(item_id TEXT PRIMARY KEY, added_at TEXT)"
        )
        self._conn.commit()

    def has(self, item_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_items WHERE item_id = ?", (item_id,)
        )
        return cur.fetchone() is not None

    def add(self, item_id: str) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT OR IGNORE INTO seen_items VALUES (?, ?)",
                    (item_id, datetime.now(timezone.utc).isoformat()),
                )
        except sqlite3.Error as e:
            raise DedupStoreError(str(e)) from e
