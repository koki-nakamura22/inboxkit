from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from notion_client import Client

from ..digester import ConfigurationError
from ..types import Digest, Item

if TYPE_CHECKING:
    from ..digester import FailureInfo


class NotionDatabaseSource:
    """Notion データベースを Source として扱い、任意で書き戻し (AckSource) も行う.

    Issue #29: ``status_property`` / ``status_value_success`` / ``status_value_failure``
    を指定すると ``ack_success`` / ``ack_failure`` 時に ``pages.update`` で Status を
    書き戻す. 未指定なら ack は no-op (既存利用者の挙動互換).

    書き戻し設定の整合性:
      ``status_property`` と ``status_value_success`` (または ``status_value_failure``)
      は **どちらも揃って指定** する必要がある. 片方のみ指定すると
      ``ConfigurationError`` で早期失敗する (silent no-op を避けるため).

    callback による上書き:
      ``properties_on_success`` / ``properties_on_failure`` が ``status_property`` と
      同じキーを返した場合、標準の Status 書き戻し値は **callback の値で上書き** される
      (``dict.update`` の意味論). ``status`` 型や ``multi_select`` 型など ``select``
      以外のプロパティ型を扱いたい場合は、本仕様を利用して callback 経由で組み立てる.
    """

    def __init__(
        self,
        database_id: str,
        token: str | None = None,
        *,
        status_property: str | None = None,
        status_value_success: str | None = None,
        status_value_failure: str | None = None,
        properties_on_success: Callable[[Item, Digest], dict[str, Any]] | None = None,
        properties_on_failure: Callable[[FailureInfo], dict[str, Any]] | None = None,
        query_filter: dict[str, Any] | None = None,
    ) -> None:
        self._database_id = database_id
        resolved = token or os.environ.get("NOTION_TOKEN")
        if not resolved:
            raise ConfigurationError("NotionDatabaseSource requires token or NOTION_TOKEN env")
        # 書き戻し設定の片方指定を早期検出 (silent no-op を避ける).
        if (status_property is None) != (
            status_value_success is None and status_value_failure is None
        ):
            # status_property のみ / status_value_* のみのケース
            if status_property is None and (
                status_value_success is not None or status_value_failure is not None
            ):
                raise ConfigurationError(
                    "NotionDatabaseSource: status_value_success/failure を指定する場合は "
                    "status_property も必須です"
                )
            if status_property is not None and (
                status_value_success is None and status_value_failure is None
            ):
                raise ConfigurationError(
                    "NotionDatabaseSource: status_property を指定する場合は "
                    "status_value_success / status_value_failure の少なくとも一方を指定してください"
                )
        self._token: str = resolved
        self._status_property = status_property
        self._status_value_success = status_value_success
        self._status_value_failure = status_value_failure
        self._properties_on_success = properties_on_success
        self._properties_on_failure = properties_on_failure
        self._query_filter = query_filter
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(auth=self._token)
        return self._client

    def fetch(self) -> Iterable[Item]:
        client = self._get_client()
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {}
            if cursor is not None:
                body["start_cursor"] = cursor
            if self._query_filter is not None:
                body["filter"] = self._query_filter
            response: Any = client.request(
                path=f"databases/{self._database_id}/query",
                method="POST",
                body=body,
            )
            for page in response["results"]:
                yield Item(id=page["id"], payload=page)
            cursor = response.get("next_cursor")
            if not cursor:
                break

    def ack_success(self, item: Item, digest: Digest) -> None:
        properties: dict[str, Any] = {}
        if self._status_property and self._status_value_success:
            properties[self._status_property] = {
                "select": {"name": self._status_value_success},
            }
        if self._properties_on_success:
            properties.update(self._properties_on_success(item, digest))
        if properties:
            self._get_client().pages.update(page_id=item.id, properties=properties)

    def ack_failure(self, failure: FailureInfo) -> None:
        properties: dict[str, Any] = {}
        if self._status_property and self._status_value_failure:
            properties[self._status_property] = {
                "select": {"name": self._status_value_failure},
            }
        if self._properties_on_failure:
            properties.update(self._properties_on_failure(failure))
        if properties:
            self._get_client().pages.update(page_id=failure.item.id, properties=properties)
