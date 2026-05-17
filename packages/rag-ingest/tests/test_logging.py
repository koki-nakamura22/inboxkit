"""Logging tests: AC-009 (structured log + PII 非出力)."""

from __future__ import annotations

import json
import logging
from typing import Any, cast
from unittest.mock import patch

import pytest

from conftest import StubChunker, StubExtractor, StubSource, StubVectorSink
from rag_ingest._upstream import Item
from rag_ingest.embedders.llm import LLMEmbedder
from rag_ingest.ingester import Ingester
from rag_ingest.logging import JsonFormatter, setup_logging

_PATCH = "rag_ingest.embedders.llm._litellm_embedding"


def _mock_resp(dim: int = 4, count: int = 1, tokens: int = 100) -> dict[str, Any]:
    return {
        "data": [{"embedding": [0.0] * dim} for _ in range(count)],
        "usage": {"prompt_tokens": tokens},
    }


class _LLMIngester(Ingester):
    def __init__(self, pii_text: str = "safe text") -> None:
        self.source = StubSource(items=[Item(id="a", payload=pii_text)])
        self.extractor = StubExtractor()
        self.chunker = StubChunker()
        self.embedder = LLMEmbedder(provider="voyage", model="voyage-3")
        self.sink = StubVectorSink()


# ---------------------------------------------------------------------------
# AC-009: embed log fields
# ---------------------------------------------------------------------------


def test_embed_log_tokens_in(caplog: pytest.LogCaptureFixture) -> None:
    with patch(_PATCH, return_value=_mock_resp(tokens=100)), caplog.at_level(logging.INFO):
        _LLMIngester().run()
    records = [r for r in caplog.records if hasattr(r, "tokens_in")]
    assert records, "expected at least one embed_completed record"
    assert cast(Any, records[0]).tokens_in == 100


def test_embed_log_latency_ms_non_negative(caplog: pytest.LogCaptureFixture) -> None:
    with patch(_PATCH, return_value=_mock_resp()), caplog.at_level(logging.INFO):
        _LLMIngester().run()
    records = [r for r in caplog.records if hasattr(r, "latency_ms")]
    assert records
    assert cast(Any, records[0]).latency_ms >= 0


def test_embed_log_provider(caplog: pytest.LogCaptureFixture) -> None:
    with patch(_PATCH, return_value=_mock_resp()), caplog.at_level(logging.INFO):
        _LLMIngester().run()
    records = [r for r in caplog.records if hasattr(r, "provider")]
    assert records
    assert cast(Any, records[0]).provider == "voyage"


def test_embed_log_model(caplog: pytest.LogCaptureFixture) -> None:
    with patch(_PATCH, return_value=_mock_resp()), caplog.at_level(logging.INFO):
        _LLMIngester().run()
    records = [r for r in caplog.records if hasattr(r, "model")]
    assert records
    assert cast(Any, records[0]).model == "voyage-3"


def test_embed_log_chunk_count(caplog: pytest.LogCaptureFixture) -> None:
    with patch(_PATCH, return_value=_mock_resp()), caplog.at_level(logging.INFO):
        _LLMIngester().run()
    records = [r for r in caplog.records if hasattr(r, "chunk_count")]
    assert records
    # StubChunker returns 1 chunk per item
    assert cast(Any, records[0]).chunk_count == 1


# ---------------------------------------------------------------------------
# AC-009: PII 非出力
# ---------------------------------------------------------------------------


def test_embed_log_no_pii_in_caplog_text(caplog: pytest.LogCaptureFixture) -> None:
    pii = "alice@example.com"
    with patch(_PATCH, return_value=_mock_resp()), caplog.at_level(logging.INFO):
        _LLMIngester(pii_text=pii).run()
    assert pii not in caplog.text


def test_embed_log_no_pii_in_any_record_message(caplog: pytest.LogCaptureFixture) -> None:
    pii = "alice@example.com"
    with patch(_PATCH, return_value=_mock_resp()), caplog.at_level(logging.INFO):
        _LLMIngester(pii_text=pii).run()
    for record in caplog.records:
        assert pii not in record.getMessage()


# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------


def test_json_formatter_basic_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord("test.logger", logging.INFO, "", 0, "hello", (), None)
    data = json.loads(formatter.format(record))
    assert data["level"] == "INFO"
    assert data["message"] == "hello"
    assert data["name"] == "test.logger"
    assert "timestamp" in data


def test_json_formatter_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "embed", (), None)
    record.tokens_in = 100
    record.latency_ms = 42.5
    record.provider = "voyage"
    record.model = "voyage-3"
    record.chunk_count = 5
    data = json.loads(formatter.format(record))
    assert data["tokens_in"] == 100
    assert data["latency_ms"] == 42.5
    assert data["provider"] == "voyage"
    assert data["model"] == "voyage-3"
    assert data["chunk_count"] == 5


def test_json_formatter_omits_absent_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    data = json.loads(formatter.format(record))
    for field in ("tokens_in", "latency_ms", "provider", "model", "chunk_count"):
        assert field not in data


def test_json_formatter_output_is_valid_json() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord("x", logging.WARNING, "", 0, "test", (), None)
    output = formatter.format(record)
    parsed = json.loads(output)
    assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# usage token extraction: missing usage key → tokens_in = 0
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# setup_logging()
# ---------------------------------------------------------------------------


def test_setup_logging_adds_handler_when_none_configured() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        root.handlers = []
        setup_logging()
        assert len(root.handlers) == 1
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_setup_logging_json_format_uses_json_formatter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_INGEST_LOG_FORMAT", "json")
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        root.handlers = []
        setup_logging()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
        monkeypatch.delenv("RAG_INGEST_LOG_FORMAT", raising=False)


def test_setup_logging_text_format_uses_standard_formatter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_INGEST_LOG_FORMAT", raising=False)
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        root.handlers = []
        setup_logging()
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_setup_logging_idempotent_does_not_add_second_handler() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        root.handlers = []
        setup_logging()
        setup_logging()
        assert len(root.handlers) == 1
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_embed_log_tokens_in_zero_when_usage_absent(caplog: pytest.LogCaptureFixture) -> None:
    mock_no_usage: dict[str, Any] = {"data": [{"embedding": [0.0] * 4}]}
    with patch(_PATCH, return_value=mock_no_usage), caplog.at_level(logging.INFO):
        _LLMIngester().run()
    records = [r for r in caplog.records if hasattr(r, "tokens_in")]
    assert records
    assert cast(Any, records[0]).tokens_in == 0
