from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

from notion_client import Client

from ..digester import ConfigurationError
from ..types import Item


class NotionDatabaseSource:
    def __init__(self, database_id: str, token: str | None = None) -> None:
        self._database_id = database_id
        resolved = token or os.environ.get("NOTION_TOKEN")
        if not resolved:
            raise ConfigurationError(
                "NotionDatabaseSource requires token or NOTION_TOKEN env"
            )
        self._token: str = resolved

    def fetch(self) -> Iterable[Item]:
        client = Client(auth=self._token)
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {}
            if cursor is not None:
                body["start_cursor"] = cursor
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
