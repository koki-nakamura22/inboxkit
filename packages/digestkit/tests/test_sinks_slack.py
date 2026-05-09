"""AC-010 (Slack): SlackSink (httpx mock)

実装ファイル: packages/digestkit/src/digestkit/sinks/slack.py
対応 SR: SR-F-004 (Sink)
"""

from __future__ import annotations

import pytest


def test_slack_sink_posts_payload_containing_summary() -> None:
    """AC-010 正常系: Webhook POST のペイロードに digest.summary が含まれる."""
    pytest.fail("not yet implemented")


def test_slack_sink_raises_on_http_error() -> None:
    """AC-010 異常系: HTTP 4xx/5xx で SinkError."""
    pytest.fail("not yet implemented")
