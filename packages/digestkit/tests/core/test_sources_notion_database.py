"""AC-008: NotionDatabaseSource (ページネーション込み)

実装ファイル: packages/digestkit/src/digestkit/sources/notion_database.py
対応 SR: SR-F-004 (Source)
Fixtures: tests/fixtures/notion/database_query_page1.json + page2.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from digestkit.digester import ConfigurationError, FailureInfo
from digestkit.protocols import AckSource
from digestkit.sources.notion_database import NotionDatabaseSource
from digestkit.types import Digest, DigestkitError, Item

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "notion"


def _load(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES / name).read_text())  # type: ignore[no-any-return]


def test_notion_database_source_fetches_first_page() -> None:
    """AC-008: 1 ページ目のレスポンスから Item を yield."""
    # Arrange
    page1 = _load("database_query_page1.json")
    single_page = {**page1, "next_cursor": None, "has_more": False}
    mock_client = MagicMock()
    mock_client.request.return_value = single_page

    # Act
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="test-token")
        items = list(source.fetch())

    # Assert
    assert len(items) == 2
    assert items[0].id == "00000000-0000-0000-0000-000000000001"
    assert items[1].id == "00000000-0000-0000-0000-000000000002"
    assert isinstance(items[0].payload, dict)


def test_notion_database_source_follows_next_cursor_for_pagination() -> None:
    """AC-008 ページネーション: next_cursor を追跡して 2 ページ目も取得、合計 3 件 yield."""
    # Arrange
    page1 = _load("database_query_page1.json")
    page2 = _load("database_query_page2.json")
    mock_client = MagicMock()
    mock_client.request.side_effect = [page1, page2]

    # Act
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="test-token")
        items = list(source.fetch())

    # Assert
    assert len(items) == 3
    assert items[0].id == "00000000-0000-0000-0000-000000000001"
    assert items[2].id == "00000000-0000-0000-0000-000000000003"
    second_call_kwargs = mock_client.request.call_args_list[1].kwargs
    assert second_call_kwargs["body"]["start_cursor"] == "cursor-page-2"


def test_notion_database_source_stops_when_next_cursor_is_null() -> None:
    """AC-008: next_cursor=null でページネーション終了 (クエリは 2 回で停止)."""
    # Arrange
    page1 = _load("database_query_page1.json")
    page2 = _load("database_query_page2.json")
    mock_client = MagicMock()
    mock_client.request.side_effect = [page1, page2]

    # Act
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="test-token")
        items = list(source.fetch())

    # Assert — next_cursor=null の page2 で停止し 3 回目は呼ばれない
    assert mock_client.request.call_count == 2
    assert len(items) == 3


def test_notion_database_source_raises_configuration_error_without_token() -> None:
    """D-101: token も NOTION_TOKEN 環境変数も無い場合は ConfigurationError。"""
    # Arrange — すべての環境変数をクリアして NOTION_TOKEN が存在しない状態にする
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ConfigurationError):
        # Act / Assert
        NotionDatabaseSource(database_id="db-id")


def test_notion_database_source_yields_empty_when_results_is_empty() -> None:
    """D-101: results=[] のレスポンスで 0 件 yield (例外なし)."""
    # Arrange
    empty_response: dict[str, object] = {
        "object": "list",
        "results": [],
        "next_cursor": None,
        "has_more": False,
    }
    mock_client = MagicMock()
    mock_client.request.return_value = empty_response

    # Act
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="test-token")
        items = list(source.fetch())

    # Assert
    assert items == []


def test_notion_database_source_uses_env_token() -> None:
    """D-006: token=None の場合は NOTION_TOKEN 環境変数から取得して Client を初期化。"""
    # Arrange
    page1 = _load("database_query_page1.json")
    single_page = {**page1, "next_cursor": None, "has_more": False}
    mock_client = MagicMock()
    mock_client.request.return_value = single_page

    # Act
    with (
        patch.dict(os.environ, {"NOTION_TOKEN": "env-token"}),
        patch("digestkit.sources.notion_database.Client", return_value=mock_client) as mock_cls,
    ):
        source = NotionDatabaseSource(database_id="db-id")
        list(source.fetch())

    # Assert — 環境変数の token で Client が初期化された
    mock_cls.assert_called_once_with(auth="env-token")


# Issue #29: AckSource 実装 (書き戻し) ---------------------------------------


def _make_digest() -> Digest:
    return Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=1, model="m")


def test_notion_database_source_implements_ack_source_protocol() -> None:
    """AckSource Protocol を structural subtyping で満たす."""
    with patch("digestkit.sources.notion_database.Client", return_value=MagicMock()):
        source = NotionDatabaseSource(database_id="db-id", token="t")
    assert isinstance(source, AckSource)


def test_notion_database_source_query_filter_is_passed_to_request() -> None:
    """query_filter 指定時、body に filter が含まれる."""
    # Arrange
    mock_client = MagicMock()
    mock_client.request.return_value = {"results": [], "next_cursor": None}
    query_filter = {"property": "Status", "select": {"equals": "未読"}}

    # Act
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t", query_filter=query_filter)
        list(source.fetch())

    # Assert
    body = mock_client.request.call_args.kwargs["body"]
    assert body["filter"] == query_filter


def test_notion_database_source_query_filter_omitted_when_unset() -> None:
    """query_filter 未指定時、body に filter キーは付かない (既存挙動)."""
    mock_client = MagicMock()
    mock_client.request.return_value = {"results": [], "next_cursor": None}
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t")
        list(source.fetch())
    body = mock_client.request.call_args.kwargs["body"]
    assert "filter" not in body


def test_ack_success_updates_status_property_when_configured() -> None:
    """status_property + status_value_success 指定時に pages.update が呼ばれる."""
    mock_client = MagicMock()
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(
            database_id="db-id",
            token="t",
            status_property="Status",
            status_value_success="処理済み",
        )
        source.ack_success(Item(id="page-1", payload={}), _make_digest())

    mock_client.pages.update.assert_called_once_with(
        page_id="page-1",
        properties={"Status": {"select": {"name": "処理済み"}}},
    )


def test_ack_failure_updates_status_property_when_configured() -> None:
    """status_property + status_value_failure 指定時に pages.update が呼ばれる."""
    mock_client = MagicMock()
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(
            database_id="db-id",
            token="t",
            status_property="Status",
            status_value_failure="失敗",
        )
        failure = FailureInfo(
            item=Item(id="page-2", payload={}),
            stage="summarize",
            error=RuntimeError("boom"),
        )
        source.ack_failure(failure)

    mock_client.pages.update.assert_called_once_with(
        page_id="page-2",
        properties={"Status": {"select": {"name": "失敗"}}},
    )


def test_ack_success_is_noop_when_no_writeback_configured() -> None:
    """書き戻し設定が無ければ ack_success は pages.update を呼ばない."""
    mock_client = MagicMock()
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t")
        source.ack_success(Item(id="page-1", payload={}), _make_digest())
    mock_client.pages.update.assert_not_called()


def test_ack_failure_is_noop_when_no_writeback_configured() -> None:
    """書き戻し設定が無ければ ack_failure は pages.update を呼ばない."""
    mock_client = MagicMock()
    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t")
        failure = FailureInfo(
            item=Item(id="page-2", payload={}),
            stage="extract",
            error=RuntimeError("x"),
        )
        source.ack_failure(failure)
    mock_client.pages.update.assert_not_called()


def test_ack_success_merges_properties_on_success_callback() -> None:
    """properties_on_success コールバックで追加プロパティを書ける."""
    mock_client = MagicMock()

    def extra(item: Item, digest: Digest) -> dict[str, Any]:
        return {"Summary": {"rich_text": [{"text": {"content": digest.summary}}]}}

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(
            database_id="db-id",
            token="t",
            status_property="Status",
            status_value_success="処理済み",
            properties_on_success=extra,
        )
        source.ack_success(Item(id="page-1", payload={}), _make_digest())

    called_props = mock_client.pages.update.call_args.kwargs["properties"]
    assert called_props["Status"] == {"select": {"name": "処理済み"}}
    assert called_props["Summary"] == {
        "rich_text": [{"text": {"content": "s"}}],
    }


def test_ack_failure_merges_properties_on_failure_callback() -> None:
    """properties_on_failure コールバックで追加プロパティを書ける."""
    mock_client = MagicMock()

    def extra(failure: FailureInfo) -> dict[str, Any]:
        return {"ErrorStage": {"select": {"name": failure.stage}}}

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(
            database_id="db-id",
            token="t",
            properties_on_failure=extra,
        )
        failure = FailureInfo(
            item=Item(id="page-2", payload={}),
            stage="write",
            error=RuntimeError("x"),
        )
        source.ack_failure(failure)

    mock_client.pages.update.assert_called_once_with(
        page_id="page-2",
        properties={"ErrorStage": {"select": {"name": "write"}}},
    )


def test_ack_success_callback_only_no_status_property() -> None:
    """status_property 未指定でも properties_on_success のみで書き戻しできる."""
    mock_client = MagicMock()

    def extra(item: Item, digest: Digest) -> dict[str, Any]:
        return {"Tag": {"select": {"name": "ok"}}}

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t", properties_on_success=extra)
        source.ack_success(Item(id="page-1", payload={}), _make_digest())

    mock_client.pages.update.assert_called_once_with(
        page_id="page-1",
        properties={"Tag": {"select": {"name": "ok"}}},
    )


def test_init_raises_when_status_property_without_values() -> None:
    """status_property のみ指定 (status_value_* なし) は ConfigurationError."""
    with (
        patch("digestkit.sources.notion_database.Client", return_value=MagicMock()),
        pytest.raises(ConfigurationError, match="status_value_success"),
    ):
        NotionDatabaseSource(database_id="db-id", token="t", status_property="Status")


def test_init_raises_when_status_value_success_without_property() -> None:
    """status_value_success のみ指定 (status_property なし) は ConfigurationError."""
    with (
        patch("digestkit.sources.notion_database.Client", return_value=MagicMock()),
        pytest.raises(ConfigurationError, match="status_property"),
    ):
        NotionDatabaseSource(database_id="db-id", token="t", status_value_success="処理済み")


def test_init_raises_when_status_value_failure_without_property() -> None:
    """status_value_failure のみ指定 (status_property なし) は ConfigurationError."""
    with (
        patch("digestkit.sources.notion_database.Client", return_value=MagicMock()),
        pytest.raises(ConfigurationError, match="status_property"),
    ):
        NotionDatabaseSource(database_id="db-id", token="t", status_value_failure="失敗")


def test_init_ok_when_status_property_with_only_success_value() -> None:
    """status_property + status_value_success のみは OK (failure は no-op で構わない)."""
    with patch("digestkit.sources.notion_database.Client", return_value=MagicMock()):
        NotionDatabaseSource(
            database_id="db-id",
            token="t",
            status_property="Status",
            status_value_success="処理済み",
        )


def test_ack_success_callback_overrides_status_property() -> None:
    """callback が status_property と同じキーを返した場合、callback の値で上書きされる."""
    mock_client = MagicMock()

    def extra(item: Item, digest: Digest) -> dict[str, Any]:
        # status 型 (新型) で上書きするユースケース
        return {"Status": {"status": {"name": "Done"}}}

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(
            database_id="db-id",
            token="t",
            status_property="Status",
            status_value_success="処理済み",
            properties_on_success=extra,
        )
        source.ack_success(Item(id="page-1", payload={}), _make_digest())

    mock_client.pages.update.assert_called_once_with(
        page_id="page-1",
        properties={"Status": {"status": {"name": "Done"}}},
    )


# Issue #35: url_property モード (A + B ハイブリッド) ---------------------------


def test_fetch_with_url_property_yields_url_string_payload() -> None:
    """url_property 指定時、payload は URL 文字列、metadata に元 page を保持する."""
    page1 = _load("database_query_page1.json")
    single_page = {**page1, "next_cursor": None, "has_more": False}
    mock_client = MagicMock()
    mock_client.request.return_value = single_page

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t", url_property="URL")
        items = list(source.fetch())

    assert len(items) == 2
    assert items[0].payload == "https://example.com/article-1"
    assert items[1].payload == "https://example.com/article-2"
    # metadata 経由で元 page を参照できる
    assert items[0].metadata is not None
    assert items[0].metadata["page"]["id"] == "00000000-0000-0000-0000-000000000001"


def test_fetch_without_url_property_keeps_legacy_payload_shape() -> None:
    """url_property 未指定時は従来通り payload=page dict、metadata=None (後方互換)."""
    page1 = _load("database_query_page1.json")
    single_page = {**page1, "next_cursor": None, "has_more": False}
    mock_client = MagicMock()
    mock_client.request.return_value = single_page

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t")
        items = list(source.fetch())

    payload: Any = items[0].payload
    assert isinstance(payload, dict)
    assert payload["id"] == "00000000-0000-0000-0000-000000000001"
    assert items[0].metadata is None


def test_fetch_with_url_property_raises_when_property_missing() -> None:
    """url_property に指定した名前がページに存在しないと DigestkitError."""
    response = {
        "object": "list",
        "results": [
            {
                "object": "page",
                "id": "page-x",
                "properties": {"Title": {"title": [{"plain_text": "x"}]}},
            }
        ],
        "next_cursor": None,
        "has_more": False,
    }
    mock_client = MagicMock()
    mock_client.request.return_value = response

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t", url_property="URL")
        with pytest.raises(DigestkitError, match="URL"):
            list(source.fetch())


def test_fetch_with_url_property_raises_when_url_value_is_null() -> None:
    """url プロパティ自体は存在するが値が None の場合も DigestkitError."""
    response = {
        "object": "list",
        "results": [
            {
                "object": "page",
                "id": "page-y",
                "properties": {"URL": {"url": None}},
            }
        ],
        "next_cursor": None,
        "has_more": False,
    }
    mock_client = MagicMock()
    mock_client.request.return_value = response

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t", url_property="URL")
        with pytest.raises(DigestkitError, match="空"):
            list(source.fetch())


def test_ack_success_callback_can_access_original_page_via_metadata() -> None:
    """url_property モードでも properties_on_success callback から元 page を参照できる."""
    mock_client = MagicMock()

    def extra(item: Item, digest: Digest) -> dict[str, Any]:
        assert item.metadata is not None
        title = item.metadata["page"]["properties"]["Title"]["title"][0]["plain_text"]
        return {"Title": {"rich_text": [{"text": {"content": title}}]}}

    page1 = _load("database_query_page1.json")
    single_page = {**page1, "next_cursor": None, "has_more": False}
    mock_client.request.return_value = single_page

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(
            database_id="db-id",
            token="t",
            url_property="URL",
            properties_on_success=extra,
        )
        items = list(source.fetch())
        source.ack_success(items[0], _make_digest())

    called_props = mock_client.pages.update.call_args.kwargs["properties"]
    assert called_props["Title"]["rich_text"][0]["text"]["content"] == "Article 1 (page 1)"
