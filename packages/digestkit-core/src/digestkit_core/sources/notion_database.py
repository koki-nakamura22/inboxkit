from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from typing import Any, cast

from notion_client import Client

from digestkit_core._notion_retry import with_retry
from digestkit_core.types import ConfigurationError, Digest, DigestkitError, FailureInfo, Item


def _extract_url_from_property(page: dict[str, Any], property_name: str) -> str:
    """Notion page object から指定プロパティの URL 文字列を取り出す.

    対応プロパティ型: ``url`` (Notion の組み込み URL 型). 値が未設定 (None) の場合や
    プロパティ自体が存在しない場合は ``DigestkitError`` を送出する.
    """
    properties = cast("dict[str, Any]", page.get("properties") or {})
    prop = properties.get(property_name)
    if prop is None:
        raise DigestkitError(
            f"NotionDatabaseSource: page {page.get('id')!r} に URL プロパティ "
            f"{property_name!r} が存在しません"
        )
    prop_dict = cast("dict[str, Any]", prop) if isinstance(prop, dict) else None
    url_value: Any = prop_dict.get("url") if prop_dict is not None else None
    if not url_value:
        raise DigestkitError(
            f"NotionDatabaseSource: page {page.get('id')!r} の URL プロパティ "
            f"{property_name!r} が空です"
        )
    return str(url_value)


class NotionDatabaseSource:
    """Notion データベースを Source として扱い、任意で書き戻し (AckSource) も行う.

    Issue #29: ``status_property`` / ``status_value_success`` / ``status_value_failure``
    を指定すると ``ack_success`` / ``ack_failure`` 時に ``pages.update`` で Status を
    書き戻す. 未指定なら ack は no-op (既存利用者の挙動互換).

    書き戻し設定の整合性:
      ``status_property`` と ``status_value_success`` (または ``status_value_failure``)
      は **どちらも揃って指定** する必要がある. 片方のみ指定すると
      ``ConfigurationError`` で早期失敗する (silent no-op を避けるため).

    URL モード (Issue #35):
      ``url_property`` を指定すると、各ページの該当 URL プロパティを取り出し
      ``Item(payload=url_string, metadata={"page": page_obj})`` を yield する.
      これにより ``WebPageExtractor`` とそのまま接続できる. callback などで元の
      Notion page object 全体を参照したい場合は ``item.metadata["page"]`` から取得する.
      未指定の場合は従来通り ``Item(payload=page_obj)`` を返す (後方互換).

    429 リトライ (Issue #42):
      ``max_retries`` (default: 3) / ``initial_backoff_sec`` (default: 1.0) で
      Notion API の 429 rate-limit に対する自動再試行を制御する. ``Retry-After``
      ヘッダがあればその秒数を尊重し、無ければ ``initial_backoff_sec * 2 ** attempt``
      の指数バックオフで sleep する. 429 以外のエラーは即時 raise する.

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
        url_property: str | None = None,
        max_retries: int = 3,
        initial_backoff_sec: float = 1.0,
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
        self._url_property = url_property
        if max_retries < 0:
            raise ConfigurationError("NotionDatabaseSource: max_retries must be >= 0")
        if initial_backoff_sec < 0:
            raise ConfigurationError("NotionDatabaseSource: initial_backoff_sec must be >= 0")
        self._max_retries = max_retries
        self._initial_backoff_sec = initial_backoff_sec
        self._client: Client | None = None
        # Issue #41: Notion 3.x Data Sources API 解決結果のキャッシュ.
        # ``_data_source_resolved`` は「解決済みか」を示すフラグで、
        # ``_data_source_id`` は新 API 用 ID (None = 旧 API で fallback)。
        # None の意味が二通り (未解決 / 解決済みだが旧 API) あるためフラグを別途持つ。
        self._data_source_resolved: bool = False
        self._data_source_id: str | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(auth=self._token)
        return self._client

    def _call(self, func: Callable[[], Any]) -> Any:
        return with_retry(
            func,
            max_retries=self._max_retries,
            initial_backoff_sec=self._initial_backoff_sec,
        )

    def _resolve_data_source_id(self) -> str | None:
        """Notion 3.x の data source ID を解決する (初回のみ API 呼び出し、以降キャッシュ).

        ``databases.retrieve`` の応答 ``data_sources`` が空でなければその先頭 ID を返す.
        空 / キー不在の場合は旧 API へ fallback すべく ``None`` を返す.
        想定外の構造 (list でない / 要素が dict でない / id が文字列でない) は
        ``DigestkitError`` で明示的に弾く.
        """
        if self._data_source_resolved:
            return self._data_source_id
        client = self._get_client()
        retrieved: Any = self._call(
            lambda: client.request(
                path=f"databases/{self._database_id}",
                method="GET",
            )
        )
        if isinstance(retrieved, dict):
            data_sources: Any = cast("dict[str, Any]", retrieved).get("data_sources")
        else:
            data_sources = None
        resolved: str | None = None
        if data_sources is not None:
            if not isinstance(data_sources, list):
                raise DigestkitError(
                    "NotionDatabaseSource: databases.retrieve の data_sources が"
                    " list ではありません"
                )
            ds_list = cast("list[Any]", data_sources)
            if ds_list:
                first: Any = ds_list[0]
                if not isinstance(first, dict):
                    raise DigestkitError(
                        "NotionDatabaseSource: data_sources[0] が dict ではありません"
                    )
                first_dict = cast("dict[str, Any]", first)
                ds_id: Any = first_dict.get("id")
                if not isinstance(ds_id, str) or not ds_id:
                    raise DigestkitError(
                        "NotionDatabaseSource: data_sources[0].id が文字列ではありません"
                    )
                resolved = ds_id
        self._data_source_id = resolved
        self._data_source_resolved = True
        return resolved

    def fetch(self) -> Iterable[Item]:
        client = self._get_client()
        data_source_id = self._resolve_data_source_id()
        if data_source_id is not None:
            query_path = f"data_sources/{data_source_id}/query"
        else:
            query_path = f"databases/{self._database_id}/query"
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {}
            if cursor is not None:
                body["start_cursor"] = cursor
            if self._query_filter is not None:
                body["filter"] = self._query_filter
            response: Any = self._call(
                lambda body=body: client.request(
                    path=query_path,
                    method="POST",
                    body=body,
                )
            )
            for page in response["results"]:
                if self._url_property is not None:
                    url = _extract_url_from_property(page, self._url_property)
                    yield Item(id=page["id"], payload=url, metadata={"page": page})
                else:
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
            client = self._get_client()
            self._call(lambda: client.pages.update(page_id=item.id, properties=properties))

    def ack_failure(self, failure: FailureInfo) -> None:
        properties: dict[str, Any] = {}
        if self._status_property and self._status_value_failure:
            properties[self._status_property] = {
                "select": {"name": self._status_value_failure},
            }
        if self._properties_on_failure:
            properties.update(self._properties_on_failure(failure))
        if properties:
            client = self._get_client()
            self._call(lambda: client.pages.update(page_id=failure.item.id, properties=properties))
