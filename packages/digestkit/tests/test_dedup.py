"""AC-014: Digester-level dedup (D-001)

実装ファイル: packages/digestkit/src/digestkit/dedup.py (or 同等)
対応 SR: SR-F-011
decision-defaults.md D-001: Digester がオプショナル属性 seen_store: SeenStore | None を持つ
                            default は SQLiteSeenStore("~/.cache/digestkit/<class>.db")
"""

from __future__ import annotations

import pytest


def test_seen_store_skips_item_on_second_run(tmp_path: object) -> None:
    """AC-014: 同一 Item.id で run() を 2 回. 2 回目で skip され RunResult.skipped == 1."""
    pytest.fail("not yet implemented")


def test_seen_store_records_id_only_after_successful_write(tmp_path: object) -> None:
    """D-001: write 失敗時は seen_store に id を追加しない (次回 run で再試行可能)."""
    pytest.fail("not yet implemented")


def test_seen_store_disabled_when_seen_store_is_none() -> None:
    """D-001: Digester(seen_store=None) で重複防止が無効化される."""
    pytest.fail("not yet implemented")


def test_default_seen_store_uses_xdg_cache_dir() -> None:
    """D-001: デフォルト seen_store の path が XDG_CACHE_HOME or ~/.cache/digestkit/<class>.db."""
    pytest.fail("not yet implemented")
