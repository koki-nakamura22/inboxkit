"""AC-009 / AC-009b / AC-R-002: SQLiteSink

実装ファイル: packages/digestkit/src/digestkit/sinks/sqlite.py
対応 SR: SR-F-004 (Sink) / SR-R-002
"""

from __future__ import annotations

import pytest


def test_sqlite_sink_writes_single_row_with_metadata(tmp_path: object) -> None:
    """AC-009: 1 件目正常書き込み. summary / item_id / tokens_in / latency_ms / model が格納."""
    pytest.fail("not yet implemented")


def test_sqlite_sink_simple_insert_for_duplicate_item_id(tmp_path: object) -> None:
    """AC-009b: 同一 item_id を 2 回 write. D-001 (Digester-level dedup) のため Sink は単純 insert (重複防止は Digester 側)."""
    pytest.fail("not yet implemented")


def test_sqlite_sink_rolls_back_on_commit_failure(tmp_path: object) -> None:
    """AC-R-002: 1 件単位 transaction. 2 件目で commit 直前に例外 → 1 件目と 3 件目のみ DB に残る."""
    pytest.fail("not yet implemented")
