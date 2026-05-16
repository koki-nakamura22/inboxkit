"""Issue #42: Notion API 429 rate-limit retry の挙動テスト.

対象: ``digestkit._notion_retry.with_retry`` + ``NotionDatabaseSource`` /
``NotionPageSink`` のコンストラクタ引数 (``max_retries`` / ``initial_backoff_sec``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from notion_client.errors import APIErrorCode, APIResponseError

from digestkit._notion_retry import with_retry
from digestkit.sinks import SinkError
from digestkit.sinks.notion_page import NotionPageSink
from digestkit.sources.notion_database import NotionDatabaseSource
from digestkit.types import Digest, Item


def _rate_limited(retry_after: str | None = None) -> APIResponseError:
    headers = httpx.Headers({"Retry-After": retry_after}) if retry_after else httpx.Headers()
    return APIResponseError(
        code=APIErrorCode.RateLimited,
        status=429,
        message="rate limited",
        headers=headers,
        raw_body_text="",
    )


def _unauthorized() -> APIResponseError:
    return APIResponseError(
        code=APIErrorCode.Unauthorized,
        status=401,
        message="nope",
        headers=httpx.Headers(),
        raw_body_text="",
    )


# --- with_retry の単体テスト -------------------------------------------------


def test_with_retry_returns_value_when_first_call_succeeds() -> None:
    sleeps: list[float] = []
    result = with_retry(lambda: "ok", max_retries=3, initial_backoff_sec=1.0, sleep=sleeps.append)
    assert result == "ok"
    assert sleeps == []


def test_with_retry_recovers_after_429_then_success() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def func() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _rate_limited()
        return "ok"

    result = with_retry(func, max_retries=3, initial_backoff_sec=1.0, sleep=sleeps.append)
    assert result == "ok"
    assert sleeps == [1.0]  # exponential backoff の初回 = initial_backoff_sec


def test_with_retry_exponential_backoff_progression() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def func() -> str:
        calls["n"] += 1
        if calls["n"] < 4:
            raise _rate_limited()
        return "ok"

    result = with_retry(func, max_retries=3, initial_backoff_sec=1.0, sleep=sleeps.append)
    assert result == "ok"
    # attempt=0,1,2 で 1.0, 2.0, 4.0
    assert sleeps == [1.0, 2.0, 4.0]


def test_with_retry_raises_after_max_retries_exceeded() -> None:
    sleeps: list[float] = []

    def func() -> str:
        raise _rate_limited()

    with pytest.raises(APIResponseError) as excinfo:
        with_retry(func, max_retries=2, initial_backoff_sec=0.5, sleep=sleeps.append)
    assert excinfo.value.status == 429
    # max_retries=2 → 3 回呼び出し、sleep は 2 回
    assert sleeps == [0.5, 1.0]


def test_with_retry_does_not_retry_non_429() -> None:
    sleeps: list[float] = []

    def func() -> str:
        raise _unauthorized()

    with pytest.raises(APIResponseError) as excinfo:
        with_retry(func, max_retries=3, initial_backoff_sec=1.0, sleep=sleeps.append)
    assert excinfo.value.status == 401
    assert sleeps == []


def test_with_retry_respects_retry_after_integer_seconds() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def func() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _rate_limited(retry_after="7")
        return "ok"

    with_retry(func, max_retries=3, initial_backoff_sec=1.0, sleep=sleeps.append)
    assert sleeps == [7.0]


def test_with_retry_respects_retry_after_http_date(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    # time.time を固定して HTTP date との差分を決定論的にする
    fixed_now = 1_700_000_000.0
    monkeypatch.setattr("digestkit._notion_retry.time.time", lambda: fixed_now)

    # fixed_now + 10s 後を HTTP date で表現
    import email.utils

    http_date = email.utils.formatdate(timeval=fixed_now + 10, usegmt=True)

    def func() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _rate_limited(retry_after=http_date)
        return "ok"

    with_retry(func, max_retries=3, initial_backoff_sec=1.0, sleep=sleeps.append)
    assert len(sleeps) == 1
    assert abs(sleeps[0] - 10.0) < 1.0


def test_with_retry_falls_back_to_backoff_on_unparseable_retry_after() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def func() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _rate_limited(retry_after="not-a-number")
        return "ok"

    with_retry(func, max_retries=3, initial_backoff_sec=2.0, sleep=sleeps.append)
    assert sleeps == [2.0]


def test_with_retry_zero_max_retries_does_not_retry() -> None:
    sleeps: list[float] = []

    def func() -> str:
        raise _rate_limited()

    with pytest.raises(APIResponseError):
        with_retry(func, max_retries=0, initial_backoff_sec=1.0, sleep=sleeps.append)
    assert sleeps == []


# --- NotionDatabaseSource 統合 -----------------------------------------------


def test_notion_database_source_retries_on_429_in_fetch() -> None:
    """fetch (data_sources/query) が 429 → 成功で 1 回 retry される."""
    mock_client = MagicMock()

    state = {"retrieve_called": False, "query_calls": 0}

    def side_effect(*, path: str, method: str, body: Any = None) -> Any:
        if method == "GET":
            state["retrieve_called"] = True
            return {"data_sources": []}
        state["query_calls"] += 1
        if state["query_calls"] == 1:
            raise _rate_limited()
        return {"results": [], "next_cursor": None}

    mock_client.request.side_effect = side_effect

    sleeps: list[float] = []
    with (
        patch("digestkit.sources.notion_database.Client", return_value=mock_client),
        patch("digestkit._notion_retry.time.sleep", side_effect=sleeps.append),
    ):
        source = NotionDatabaseSource(
            database_id="db-id", token="t", max_retries=3, initial_backoff_sec=0.5
        )
        list(source.fetch())

    assert state["query_calls"] == 2
    assert sleeps == [0.5]


def test_notion_database_source_propagates_non_429() -> None:
    mock_client = MagicMock()

    def side_effect(*, path: str, method: str, body: Any = None) -> Any:
        if method == "GET":
            raise _unauthorized()
        return {"results": [], "next_cursor": None}

    mock_client.request.side_effect = side_effect

    with patch("digestkit.sources.notion_database.Client", return_value=mock_client):
        source = NotionDatabaseSource(database_id="db-id", token="t")
        with pytest.raises(APIResponseError) as excinfo:
            list(source.fetch())
        assert excinfo.value.status == 401


def test_notion_database_source_ack_success_retries_on_429() -> None:
    mock_client = MagicMock()
    calls = {"n": 0}

    def update(**kwargs: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _rate_limited()
        return {"ok": True}

    mock_client.pages.update.side_effect = update

    sleeps: list[float] = []
    with (
        patch("digestkit.sources.notion_database.Client", return_value=mock_client),
        patch("digestkit._notion_retry.time.sleep", side_effect=sleeps.append),
    ):
        source = NotionDatabaseSource(
            database_id="db-id",
            token="t",
            status_property="Status",
            status_value_success="処理済み",
            max_retries=2,
            initial_backoff_sec=0.25,
        )
        digest = Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=1, model="m")
        source.ack_success(Item(id="page-1", payload={}), digest)

    assert calls["n"] == 2
    assert sleeps == [0.25]


def test_notion_database_source_raises_when_max_retries_negative() -> None:
    from digestkit.digester import ConfigurationError

    with (
        patch("digestkit.sources.notion_database.Client", return_value=MagicMock()),
        pytest.raises(ConfigurationError, match="max_retries"),
    ):
        NotionDatabaseSource(database_id="db-id", token="t", max_retries=-1)


# --- NotionPageSink 統合 -----------------------------------------------------


def test_notion_page_sink_retries_on_429() -> None:
    mock_client = MagicMock()
    calls = {"n": 0}

    def append(**kwargs: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _rate_limited()
        return {"ok": True}

    mock_client.blocks.children.append.side_effect = append

    sleeps: list[float] = []
    with (
        patch("digestkit.sinks.notion_page.Client", return_value=mock_client),
        patch("digestkit._notion_retry.time.sleep", side_effect=sleeps.append),
    ):
        sink = NotionPageSink(token="t", max_retries=2, initial_backoff_sec=0.1)
        sink.write(
            Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=1, model="m"),
            Item(id="page-1", payload=None),
        )

    assert calls["n"] == 2
    assert sleeps == [0.1]


def test_notion_page_sink_wraps_429_in_sink_error_after_exceeding_retries() -> None:
    """max_retries を超えた 429 は SinkError でラップされる (既存挙動を維持)."""
    mock_client = MagicMock()
    mock_client.blocks.children.append.side_effect = _rate_limited()

    sleeps: list[float] = []
    with (
        patch("digestkit.sinks.notion_page.Client", return_value=mock_client),
        patch("digestkit._notion_retry.time.sleep", side_effect=sleeps.append),
    ):
        sink = NotionPageSink(token="t", max_retries=1, initial_backoff_sec=0.01)
        with pytest.raises(SinkError, match="rate limited"):
            sink.write(
                Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=1, model="m"),
                Item(id="page-1", payload=None),
            )
    # 1 回 retry → 計 2 回呼び出し → sleep は 1 回
    assert mock_client.blocks.children.append.call_count == 2
    assert sleeps == [0.01]


def test_notion_page_sink_does_not_retry_non_429() -> None:
    mock_client = MagicMock()
    mock_client.blocks.children.append.side_effect = _unauthorized()

    sleeps: list[float] = []
    with (
        patch("digestkit.sinks.notion_page.Client", return_value=mock_client),
        patch("digestkit._notion_retry.time.sleep", side_effect=sleeps.append),
    ):
        sink = NotionPageSink(token="t")
        with pytest.raises(SinkError):
            sink.write(
                Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=1, model="m"),
                Item(id="page-1", payload=None),
            )
    assert mock_client.blocks.children.append.call_count == 1
    assert sleeps == []
