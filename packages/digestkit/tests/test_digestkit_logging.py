"""AC-012: 構造化ログ + PII 非出力

実装ファイル: packages/digestkit/src/digestkit/logging.py + LLMSummarizer 内のログ出力
対応 SR: SR-F-008 / SR-Sec-002
"""

from __future__ import annotations

import io
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from digestkit.logging import get_logger
from digestkit.summarizers.llm import LLMSummarizer
from digestkit.types import Item

_PATCH = "digestkit.summarizers.llm.litellm.completion"
_LOGGER_NAME = "digestkit.summarizers.llm"


def _make_mock_response(
    summary: str = "generic summary",
    tokens_in: int = 100,
    tokens_out: int = 50,
) -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = summary
    mock.usage.prompt_tokens = tokens_in
    mock.usage.completion_tokens = tokens_out
    return mock


def _make_summarizer() -> LLMSummarizer:
    return LLMSummarizer(provider="openai", model="gpt-4")


def _make_item() -> Item:
    return Item(id="item-1", payload=None)


def test_llm_log_record_contains_required_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-012: LLM 呼び出しログに tokens_in/out / latency_ms / provider / model の 5 フィールド."""
    # Arrange
    summarizer = _make_summarizer()
    item = _make_item()
    mock_response = _make_mock_response()

    # Act
    with (
        patch(_PATCH, return_value=mock_response),
        caplog.at_level(logging.INFO, logger=_LOGGER_NAME),
    ):
        summarizer.summarize("some text", item)

    # Assert
    completed = [r for r in caplog.records if r.getMessage() == "llm_call_completed"]
    assert completed, "No 'llm_call_completed' record captured"
    record = completed[0]
    attrs = record.__dict__
    assert "tokens_in" in attrs
    assert "tokens_out" in attrs
    assert "latency_ms" in attrs
    assert "provider" in attrs
    assert "model" in attrs


def test_log_does_not_contain_pii_email(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-012 / SR-Sec-002: 本文に alice@example.com を含めてもどのレコードにも出ない."""
    # Arrange
    pii = "alice@example.com"
    mock_response = _make_mock_response(summary=f"Summary for {pii}")

    # Act
    with (
        patch(_PATCH, return_value=mock_response),
        caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME),
    ):
        _make_summarizer().summarize(f"Contact {pii} for details.", _make_item())

    # Assert
    for record in caplog.records:
        record_text = json.dumps(record.__dict__, default=str)
        assert pii not in record_text


def test_log_does_not_contain_pii_ssn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-012 / SR-Sec-002: 本文に SSN 風文字列 (123-45-6789) を含めても、ログに出ない."""
    # Arrange
    pii = "123-45-6789"
    mock_response = _make_mock_response(summary=f"SSN: {pii}")

    # Act
    with (
        patch(_PATCH, return_value=mock_response),
        caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME),
    ):
        _make_summarizer().summarize(f"SSN: {pii}", _make_item())

    # Assert
    for record in caplog.records:
        record_text = json.dumps(record.__dict__, default=str)
        assert pii not in record_text


def test_log_does_not_contain_summary_body_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-012 / SR-Sec-002: 本文の主要部分そのものがログに出ない."""
    # Arrange
    body = "UNIQUE_BODY_TEXT_FOR_LOGGING_TEST_XYZ_99999"
    mock_response = _make_mock_response(summary=body)

    # Act
    with (
        patch(_PATCH, return_value=mock_response),
        caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME),
    ):
        _make_summarizer().summarize(body, _make_item())

    # Assert
    for record in caplog.records:
        record_text = json.dumps(record.__dict__, default=str)
        assert body not in record_text


def test_log_format_json_produces_valid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-012: DIGESTKIT_LOG_FORMAT=json でレコードが JSON parse 可能."""
    # Arrange — env var を設定してから新規ロガーを取得 (idempotency 回避のため一意名を使う)
    monkeypatch.setenv("DIGESTKIT_LOG_FORMAT", "json")
    unique_name = f"digestkit.test.json_format.{id(monkeypatch)}"
    logger = get_logger(unique_name)
    stream = io.StringIO()
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.stream = stream

    # Act
    logger.info(
        "llm_call_completed",
        extra={
            "tokens_in": 100,
            "tokens_out": 50,
            "latency_ms": 200,
            "provider": "openai",
            "model": "openai/gpt-4",
        },
    )

    # Assert — 出力全体が valid JSON かつ必須フィールドを含む
    output = stream.getvalue().strip()
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "llm_call_completed"
    assert parsed["tokens_in"] == 100
    assert parsed["tokens_out"] == 50
    assert parsed["latency_ms"] == 200
    assert parsed["provider"] == "openai"
    assert parsed["model"] == "openai/gpt-4"
