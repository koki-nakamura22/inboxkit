"""AC-008: NotionDatabaseSource (ページネーション込み)

実装ファイル: packages/digestkit/src/digestkit/sources/notion_database.py
対応 SR: SR-F-004 (Source)
Fixtures: tests/fixtures/notion/database_query_page1.json + page2.json
"""

from __future__ import annotations

import pytest


def test_notion_database_source_fetches_first_page() -> None:
    """AC-008: 1 ページ目のレスポンスから Item を yield."""
    pytest.fail("not yet implemented")


def test_notion_database_source_follows_next_cursor_for_pagination() -> None:
    """AC-008 境界値: next_cursor を追跡して 2 ページ目も取得。150 件全て yield."""
    pytest.fail("not yet implemented")


def test_notion_database_source_stops_when_next_cursor_is_null() -> None:
    """AC-008: next_cursor=null でページネーション終了."""
    pytest.fail("not yet implemented")
