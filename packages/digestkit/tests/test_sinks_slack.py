"""AC-010 (Slack): SlackSink (httpx mock)

実装ファイル: packages/digestkit/src/digestkit/sinks/slack.py
対応 SR: SR-F-004 (Sink)
"""

from __future__ import annotations

import json

import httpx
import pytest

from digestkit.digester import ConfigurationError
from digestkit.sinks import SinkError
from digestkit.sinks.slack import SlackSink
from digestkit.types import Digest, Item

_WEBHOOK_URL = "https://hooks.slack.com/services/test"


def _make_digest(**kwargs: object) -> Digest:
    defaults: dict[str, object] = {
        "summary": "test summary",
        "tokens_in": 100,
        "tokens_out": 50,
        "latency_ms": 200,
        "model": "claude-3",
    }
    defaults.update(kwargs)
    return Digest(**defaults)  # type: ignore[arg-type]


def _make_item(item_id: str = "item-001") -> Item:
    return Item(id=item_id, payload=None)


def _make_sink(**kwargs: object) -> SlackSink:
    defaults: dict[str, object] = {"webhook_url": _WEBHOOK_URL}
    defaults.update(kwargs)
    return SlackSink(**defaults)  # type: ignore[arg-type]


def _capture_transport() -> tuple[httpx.MockTransport, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, text="ok")

    return httpx.MockTransport(handler), captured


def _error_transport(status_code: int) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="error")

    return httpx.MockTransport(handler)


def test_slack_sink_posts_payload_containing_summary() -> None:
    """AC-010 正常系: Webhook POST のペイロードに digest.summary が含まれる."""
    # Arrange
    transport, captured = _capture_transport()
    digest = _make_digest(summary="important summary text")
    item = _make_item("item-xyz")
    sink = _make_sink(_transport=transport)

    # Act
    sink.write(digest, item)

    # Assert
    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert "important summary text" in body["text"]


def test_slack_sink_payload_contains_item_id() -> None:
    """POST ペイロードの text に item.id が含まれる."""
    # Arrange
    transport, captured = _capture_transport()
    digest = _make_digest()
    item = _make_item("my-article-42")
    sink = _make_sink(_transport=transport)

    # Act
    sink.write(digest, item)

    # Assert
    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert "my-article-42" in body["text"]


def test_slack_sink_posts_to_webhook_url() -> None:
    """POST 先の URL が webhook_url と一致する."""
    # Arrange
    transport, captured = _capture_transport()
    sink = _make_sink(_transport=transport)

    # Act
    sink.write(_make_digest(), _make_item())

    # Assert
    assert str(captured[0].url) == _WEBHOOK_URL


def test_slack_sink_raises_on_4xx_error() -> None:
    """AC-010 異常系: HTTP 4xx で SinkError."""
    # Arrange
    sink = _make_sink(_transport=_error_transport(400))

    # Act / Assert
    with pytest.raises(SinkError):
        sink.write(_make_digest(), _make_item())


def test_slack_sink_raises_on_5xx_error() -> None:
    """AC-010 異常系: HTTP 5xx で SinkError."""
    # Arrange
    sink = _make_sink(_transport=_error_transport(500))

    # Act / Assert
    with pytest.raises(SinkError):
        sink.write(_make_digest(), _make_item())


def test_slack_sink_raises_on_network_error() -> None:
    """ネットワーク接続失敗で SinkError."""
    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    sink = _make_sink(_transport=httpx.MockTransport(handler))

    # Act / Assert
    with pytest.raises(SinkError):
        sink.write(_make_digest(), _make_item())


def test_slack_sink_raises_configuration_error_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """webhook_url=None かつ SLACK_WEBHOOK_URL 未設定 → ConfigurationError."""
    # Arrange
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    # Act / Assert
    with pytest.raises(ConfigurationError):
        SlackSink(webhook_url=None)


def test_slack_sink_raises_configuration_error_for_http_url() -> None:
    """http:// URL (非 HTTPS) → ConfigurationError."""
    # Act / Assert
    with pytest.raises(ConfigurationError):
        SlackSink(webhook_url="http://hooks.slack.com/services/test")


def test_slack_sink_raises_configuration_error_for_empty_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """webhook_url="" かつ SLACK_WEBHOOK_URL 未設定 → Falsy フォールバック後に ConfigurationError."""
    # Arrange
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    # Act / Assert
    with pytest.raises(ConfigurationError):
        SlackSink(webhook_url="")


def test_slack_sink_uses_env_var_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """webhook_url=None のとき SLACK_WEBHOOK_URL 環境変数を使う."""
    # Arrange
    monkeypatch.setenv("SLACK_WEBHOOK_URL", _WEBHOOK_URL)
    transport, captured = _capture_transport()
    sink = SlackSink(webhook_url=None, _transport=transport)

    # Act
    sink.write(_make_digest(), _make_item())

    # Assert
    assert len(captured) == 1
