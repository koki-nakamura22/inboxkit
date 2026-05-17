from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from notion_client import Client

from digestkit_core._notion_retry import with_retry

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

    注意点:
      - **冪等性なし**: ``blocks.children.append`` は文字通り「追記」であり、同じ item
        に対して 2 回 ``write`` を呼ぶとブロックが 2 回追記される. 重複防止は本 Sink
        の責務外で、呼び出し側 (例: ``NotionDatabaseSource`` の ``query_filter`` で
        Status=未読 のみを対象にする運用) で担保する.
      - **1 リクエスト 100 ブロック上限**: Notion API の ``blocks.children.append``
        は 1 回の呼び出しで最大 100 ブロックまで. ``blocks_builder`` が 100 を超える
        ブロックを返した場合、Notion API がエラーを返し ``SinkError`` でラップされる.

    429 リトライ (Issue #42):
      ``max_retries`` (default: 3) / ``initial_backoff_sec`` (default: 1.0) で 429
      rate-limit に対する自動再試行を制御する. ``Retry-After`` ヘッダがあればその秒数を
      尊重し、無ければ指数バックオフ. 429 以外のエラーは従来通り ``SinkError`` で
      ラップして即時 raise する.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        blocks_builder: Callable[[Digest, Item], list[dict[str, Any]]] | None = None,
        max_retries: int = 3,
        initial_backoff_sec: float = 1.0,
    ) -> None:
        resolved = token or os.environ.get("NOTION_TOKEN")
        if not resolved:
            raise ConfigurationError("NotionPageSink requires token or NOTION_TOKEN env")
        if max_retries < 0:
            raise ConfigurationError("NotionPageSink: max_retries must be >= 0")
        if initial_backoff_sec < 0:
            raise ConfigurationError("NotionPageSink: initial_backoff_sec must be >= 0")
        self._token: str = resolved
        self._blocks_builder = blocks_builder
        self._max_retries = max_retries
        self._initial_backoff_sec = initial_backoff_sec
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(auth=self._token)
        return self._client

    def write(self, digest: Digest, item: Item) -> None:
        builder = self._blocks_builder or _default_blocks_builder
        blocks = builder(digest, item)
        client = self._get_client()
        try:
            with_retry(
                lambda: client.blocks.children.append(block_id=item.id, children=blocks),
                max_retries=self._max_retries,
                initial_backoff_sec=self._initial_backoff_sec,
            )
        except Exception as e:
            raise SinkError(str(e)) from e
