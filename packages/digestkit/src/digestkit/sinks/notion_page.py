from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from notion_client import Client

from ..digester import ConfigurationError
from ..types import Digest, Item
from . import SinkError


def _default_blocks_builder(digest: Digest, item: Item) -> list[dict[str, Any]]:
    return [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "要約"}}],
            },
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": digest.summary}}],
            },
        },
    ]


class NotionPageSink:
    """Notion ページ本文 (children blocks) に digest 内容を追記する Sink.

    ``item.id`` を Notion ページ ID と見なし、``blocks.children.append`` を呼ぶ.
    ``NotionDatabaseSource`` (= Item.id がページ ID) と組み合わせて使うことを想定する.

    ``blocks_builder`` 未指定時は ``heading_2`` + ``paragraph`` の 2 ブロックを
    デフォルトで追記する. 「箇条書き要点 + トグル付き本文」等の複雑な構造を
    組みたい場合は独自の builder を渡す.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        blocks_builder: Callable[[Digest, Item], list[dict[str, Any]]] | None = None,
    ) -> None:
        resolved = token or os.environ.get("NOTION_TOKEN")
        if not resolved:
            raise ConfigurationError("NotionPageSink requires token or NOTION_TOKEN env")
        self._token: str = resolved
        self._blocks_builder = blocks_builder
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(auth=self._token)
        return self._client

    def write(self, digest: Digest, item: Item) -> None:
        builder = self._blocks_builder or _default_blocks_builder
        blocks = builder(digest, item)
        try:
            self._get_client().blocks.children.append(block_id=item.id, children=blocks)
        except Exception as e:
            raise SinkError(str(e)) from e
