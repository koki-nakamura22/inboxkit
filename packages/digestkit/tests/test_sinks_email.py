"""AC-010 (Email): EmailSink (smtplib mock)

実装ファイル: packages/digestkit/src/digestkit/sinks/email.py
対応 SR: SR-F-004 (Sink)
"""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from digestkit.sinks import SinkError
from digestkit.sinks.email import EmailSink
from digestkit.types import Digest, Item


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


def _make_sink(**kwargs: object) -> EmailSink:
    defaults: dict[str, object] = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "sender": "sender@example.com",
        "recipients": ["recipient@example.com"],
        "username": "user",
        "password": "pass",
    }
    defaults.update(kwargs)
    return EmailSink(**defaults)  # type: ignore[arg-type]


def _mock_smtp() -> tuple[MagicMock, MagicMock]:
    """Return (mock_smtp_class, mock_smtp_instance)."""
    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance
    mock_smtp_class.return_value.__exit__.return_value = False
    return mock_smtp_class, mock_smtp_instance


def test_email_sink_sends_payload_containing_summary() -> None:
    """AC-010 正常系: 送信ペイロードに digest.summary が含まれる."""
    # Arrange
    digest = _make_digest(summary="important summary")
    item = _make_item("item-xyz")
    sink = _make_sink()
    mock_smtp_class, mock_smtp_instance = _mock_smtp()

    # Act
    with patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class):
        sink.write(digest, item)

    # Assert
    mock_smtp_instance.send_message.assert_called_once()
    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
    assert "important summary" in sent_msg.get_payload()


def test_email_sink_raises_on_smtp_failure() -> None:
    """AC-010 異常系: SMTP 失敗時に SinkError (DigestkitError 階層) を投げる."""
    # Arrange
    digest = _make_digest()
    item = _make_item()
    sink = _make_sink()
    mock_smtp_class = MagicMock()
    mock_smtp_class.return_value.__enter__.side_effect = smtplib.SMTPException("connection refused")

    # Act / Assert
    with pytest.raises(SinkError), patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class):
        sink.write(digest, item)


def test_email_sink_calls_starttls_when_use_tls_true() -> None:
    """use_tls=True (デフォルト) のとき starttls() が呼ばれる."""
    # Arrange
    sink = _make_sink(use_tls=True)
    mock_smtp_class, mock_smtp_instance = _mock_smtp()

    # Act
    with patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class):
        sink.write(_make_digest(), _make_item())

    # Assert
    mock_smtp_instance.starttls.assert_called_once()


def test_email_sink_skips_starttls_when_use_tls_false() -> None:
    """use_tls=False のとき starttls() は呼ばれない."""
    # Arrange
    sink = _make_sink(use_tls=False)
    mock_smtp_class, mock_smtp_instance = _mock_smtp()

    # Act
    with patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class):
        sink.write(_make_digest(), _make_item())

    # Assert
    mock_smtp_instance.starttls.assert_not_called()


def test_email_sink_calls_login_when_credentials_provided() -> None:
    """username/password が与えられているとき login() が呼ばれる."""
    # Arrange
    sink = _make_sink(username="myuser", password="mypass")
    mock_smtp_class, mock_smtp_instance = _mock_smtp()

    # Act
    with patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class):
        sink.write(_make_digest(), _make_item())

    # Assert
    mock_smtp_instance.login.assert_called_once_with("myuser", "mypass")


def test_email_sink_skips_login_when_no_credentials() -> None:
    """username/password が None のとき login() は呼ばれない."""
    # Arrange
    sink = _make_sink(username=None, password=None)
    mock_smtp_class, mock_smtp_instance = _mock_smtp()

    # Act
    with (
        patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class),
        patch.dict("os.environ", {}, clear=True),
    ):
        # EMAIL_USERNAME / EMAIL_PASSWORD も未設定
        import os

        os.environ.pop("EMAIL_USERNAME", None)
        os.environ.pop("EMAIL_PASSWORD", None)
        sink.write(_make_digest(), _make_item())

    # Assert
    mock_smtp_instance.login.assert_not_called()


def test_email_sink_uses_env_vars_when_credentials_not_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """username/password が None のとき環境変数 EMAIL_USERNAME/EMAIL_PASSWORD を使う."""
    # Arrange
    monkeypatch.setenv("EMAIL_USERNAME", "env_user")
    monkeypatch.setenv("EMAIL_PASSWORD", "env_pass")
    sink = _make_sink(username=None, password=None)
    mock_smtp_class, mock_smtp_instance = _mock_smtp()

    # Act
    with patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class):
        sink.write(_make_digest(), _make_item())

    # Assert
    mock_smtp_instance.login.assert_called_once_with("env_user", "env_pass")


def test_email_sink_smtp_auth_failure_raises_sink_error() -> None:
    """login() が SMTPAuthenticationError を投げたとき SinkError が伝播する."""
    # Arrange
    sink = _make_sink()
    mock_smtp_class, mock_smtp_instance = _mock_smtp()
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

    # Act / Assert
    with pytest.raises(SinkError), patch("digestkit.sinks.email.smtplib.SMTP", mock_smtp_class):
        sink.write(_make_digest(), _make_item())
