"""AC-009 / AC-009b / AC-R-002: SQLiteSink

実装ファイル: packages/digestkit/src/digestkit/sinks/sqlite.py
対応 SR: SR-F-004 (Sink) / SR-R-002
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from digestkit.sinks import SinkError
from digestkit.sinks.sqlite import SQLiteSink
from digestkit.types import Digest, Item


def _make_digest(**kwargs: object) -> Digest:
    defaults: dict[str, object] = {
        "summary": "test summary",
        "tokens_in": 100,
        "tokens_out": 50,
        "latency_ms": 200,
        "model": "gpt-4o",
    }
    defaults.update(kwargs)
    return Digest(**defaults)  # type: ignore[arg-type]


def _make_item(item_id: str = "item-001") -> Item:
    return Item(id=item_id, payload=None)


def _fetch_all(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM digests ORDER BY rowid").fetchall()
    conn.close()
    return rows


def test_sqlite_sink_writes_single_row_with_metadata(tmp_path: Path) -> None:
    """AC-009: 1 件目正常書き込み. summary / item_id / tokens_in / latency_ms / model が格納."""
    db = tmp_path / "test.db"
    sink = SQLiteSink(db)
    digest = _make_digest(summary="hello world", tokens_in=42, latency_ms=300, model="claude-3")
    item = _make_item("item-abc")

    sink.write(digest, item)

    rows = _fetch_all(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["item_id"] == "item-abc"
    assert row["summary"] == "hello world"
    assert row["tokens_in"] == 42
    assert row["latency_ms"] == 300
    assert row["tokens_out"] == 50
    assert row["model"] == "claude-3"
    ts = datetime.fromisoformat(row["created_at"])
    assert ts.tzinfo is not None  # D-105: UTC offset が付いていること


def test_sqlite_sink_simple_insert_for_duplicate_item_id(tmp_path: Path) -> None:
    """AC-009b: 同一 item_id を 2 回 write. D-001 により Sink は単純 insert (dedup は Digester)."""
    db = tmp_path / "test.db"
    sink = SQLiteSink(db)
    item = _make_item("dup-id")
    digest = _make_digest()

    sink.write(digest, item)
    sink.write(digest, item)

    rows = _fetch_all(db)
    assert len(rows) == 2
    assert all(r["item_id"] == "dup-id" for r in rows)


def test_sqlite_sink_rolls_back_on_commit_failure(tmp_path: Path) -> None:
    """AC-R-002: 1 件単位 tx. 2 件目で execute 例外 → ロールバックされ 1 件目と 3 件目のみ残る."""
    db = tmp_path / "test.db"
    sink = SQLiteSink(db)

    item1 = _make_item("item-1")
    item2 = _make_item("item-2")
    item3 = _make_item("item-3")
    digest = _make_digest()

    sink.write(digest, item1)

    # sqlite3.Connection は immutable C 型なのでクラスレベルのパッチ不可。
    # sink._conn をスパイ実装で差し替え、2件目の INSERT だけ失敗させる。
    real_conn = sink._conn  # pyright: ignore[reportPrivateUsage]
    insert_count = 0

    class _SpyConn:
        def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
            nonlocal insert_count
            if "INSERT" in sql:
                insert_count += 1
                if insert_count == 1:
                    raise sqlite3.OperationalError("simulated failure")
            return real_conn.execute(sql, *args)  # type: ignore[return-value]

        def __enter__(self) -> _SpyConn:
            real_conn.__enter__()
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> object:
            return real_conn.__exit__(exc_type, exc_val, exc_tb)  # type: ignore[return-value]

    sink._conn = _SpyConn()  # type: ignore[assignment]  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(SinkError):
        sink.write(digest, item2)

    sink._conn = real_conn  # pyright: ignore[reportPrivateUsage]
    sink.write(digest, item3)

    rows = _fetch_all(db)
    ids = [r["item_id"] for r in rows]
    assert ids == ["item-1", "item-3"]
