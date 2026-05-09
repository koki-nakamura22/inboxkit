from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ..types import Digest, Item
from . import SinkError

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS digests ("
    "item_id TEXT, summary TEXT, tokens_in INT, tokens_out INT, "
    "latency_ms INT, model TEXT, created_at TEXT)"
)
_INSERT = "INSERT INTO digests VALUES (?, ?, ?, ?, ?, ?, ?)"


class SQLiteSink:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def write(self, digest: Digest, item: Item) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    _INSERT,
                    (
                        item.id,
                        digest.summary,
                        digest.tokens_in,
                        digest.tokens_out,
                        digest.latency_ms,
                        digest.model,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except sqlite3.Error as e:
            raise SinkError(str(e)) from e
