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
