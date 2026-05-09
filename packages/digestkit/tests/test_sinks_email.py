"""AC-010 (Email): EmailSink (smtplib mock)

実装ファイル: packages/digestkit/src/digestkit/sinks/email.py
対応 SR: SR-F-004 (Sink)
"""

from __future__ import annotations

import pytest


def test_email_sink_sends_payload_containing_summary() -> None:
    """AC-010 正常系: 送信ペイロードに digest.summary が含まれる."""
    pytest.fail("not yet implemented")


def test_email_sink_raises_on_smtp_failure() -> None:
    """AC-010 異常系: SMTP 失敗時に SinkError (DigestkitError 階層) を投げる."""
    pytest.fail("not yet implemented")
