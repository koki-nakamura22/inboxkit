"""NotionPageSink (Issue #30): Notion ページ本文 (children blocks) への書き戻し.

実装ファイル: packages/digestkit/src/digestkit/sinks/notion_page.py
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from digestkit.digester import ConfigurationError
from digestkit.sinks import SinkError
from digestkit.sinks.notion_page import NotionPageSink
from digestkit.types import Digest, Item


def _make_digest(summary: str = "要約テキスト") -> Digest:
    return Digest(summary=summary, tokens_in=10, tokens_out=5, latency_ms=100, model="m")


def _make_item(item_id: str = "page-1") -> Item:
    return Item(id=item_id, payload=None)


def test_notion_page_sink_appends_default_blocks() -> None:
    """デフォルト builder で heading_2 + paragraph が append される."""
    mock_client = MagicMock()
    with patch("digestkit.sinks.notion_page.Client", return_value=mock_client):
        sink = NotionPageSink(token="t")
        sink.write(_make_digest("hello summary"), _make_item("page-xyz"))

    mock_client.blocks.children.append.assert_called_once()
    kwargs = mock_client.blocks.children.append.call_args.kwargs
    assert kwargs["block_id"] == "page-xyz"
    blocks = kwargs["children"]
    assert len(blocks) == 2
    assert blocks[0]["type"] == "heading_2"
    assert blocks[0]["heading_2"]["rich_text"][0]["text"]["content"] == "要約"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["paragraph"]["rich_text"][0]["text"]["content"] == "hello summary"


def test_notion_page_sink_uses_custom_blocks_builder() -> None:
    """blocks_builder を渡すと、その結果がそのまま children として渡される."""
    mock_client = MagicMock()

    def builder(digest: Digest, item: Item) -> list[dict[str, Any]]:
        return [
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"{item.id}: {digest.summary}"}}
                    ]
                },
            }
        ]

    with patch("digestkit.sinks.notion_page.Client", return_value=mock_client):
        sink = NotionPageSink(token="t", blocks_builder=builder)
        sink.write(_make_digest("s"), _make_item("p1"))

    kwargs = mock_client.blocks.children.append.call_args.kwargs
    assert kwargs["block_id"] == "p1"
    assert kwargs["children"] == [
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "p1: s"}}]},
        }
    ]


def test_notion_page_sink_wraps_notion_exception_in_sink_error() -> None:
    """notion_client の例外は SinkError でラップされる."""
    mock_client = MagicMock()
    mock_client.blocks.children.append.side_effect = RuntimeError("notion api boom")

    with patch("digestkit.sinks.notion_page.Client", return_value=mock_client):
        sink = NotionPageSink(token="t")
        with pytest.raises(SinkError, match="notion api boom"):
            sink.write(_make_digest(), _make_item())


def test_notion_page_sink_requires_token() -> None:
    """token / NOTION_TOKEN いずれも無ければ ConfigurationError."""
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ConfigurationError):
        NotionPageSink()


def test_notion_page_sink_uses_env_token() -> None:
    """token=None の場合 NOTION_TOKEN を使って Client を初期化."""
    mock_client = MagicMock()
    with (
        patch.dict(os.environ, {"NOTION_TOKEN": "env-token"}),
        patch("digestkit.sinks.notion_page.Client", return_value=mock_client) as mock_cls,
    ):
        sink = NotionPageSink()
        sink.write(_make_digest(), _make_item())

    mock_cls.assert_called_once_with(auth="env-token")
