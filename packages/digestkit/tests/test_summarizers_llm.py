"""AC-003 / AC-003a / AC-003b: LLMSummarizer (LiteLLM mock)

実装ファイル: packages/digestkit/src/digestkit/summarizers/llm.py
対応 SR: SR-F-003
Fixtures: tests/fixtures/litellm/completion_basic.json
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from digestkit.summarizers.llm import LLMSummarizer, SummarizationError
from digestkit.types import Item

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "litellm" / "completion_basic.json").read_text()
)

_PROVIDER = "openai"
_MODEL = "gpt-4"
_FULL_MODEL = f"{_PROVIDER}/{_MODEL}"
_PATCH = "digestkit.summarizers.llm.litellm.completion"


def _make_mock_response() -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = _FIXTURE["choices"][0]["message"]["content"]
    mock.usage.prompt_tokens = _FIXTURE["usage"]["prompt_tokens"]
    mock.usage.completion_tokens = _FIXTURE["usage"]["completion_tokens"]
    return mock


def test_llm_summarizer_calls_litellm_with_expanded_prompt() -> None:
    """AC-003: user_prompt_template の {text} 展開後に litellm.completion へ渡される."""
    # Arrange
    summarizer = LLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        user_prompt_template="Summarize: {text}",
    )
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("hello world", item)

    # Assert
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args.kwargs
    messages = call_kwargs["messages"]
    user_message = next(m for m in messages if m["role"] == "user")
    assert user_message["content"] == "Summarize: hello world"
    assert call_kwargs["model"] == _FULL_MODEL


def test_llm_summarizer_returns_digest_with_metadata() -> None:
    """AC-003: 戻り値 Digest に summary / tokens_in / tokens_out / latency_ms / model が記録."""
    # Arrange
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL)
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response):
        digest = summarizer.summarize("some text", item)

    # Assert
    assert digest.summary == _FIXTURE["choices"][0]["message"]["content"]
    assert digest.tokens_in == _FIXTURE["usage"]["prompt_tokens"]
    assert digest.tokens_out == _FIXTURE["usage"]["completion_tokens"]
    assert digest.latency_ms >= 0
    assert digest.model == _FULL_MODEL


def test_llm_summarizer_handles_empty_text_input() -> None:
    """AC-003a: 空文字入力で例外を投げず LiteLLM 呼び出し成功."""
    # Arrange
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL)
    item = Item(id="item-empty", payload=None)
    mock_response = _make_mock_response()

    # Act / Assert — 例外が発生しないことを確認
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("", item)

    mock_completion.assert_called_once()


def test_llm_summarizer_passes_large_text_without_truncation() -> None:
    """AC-003b: 100,000 文字入力をそのまま LiteLLM へ渡す (フレームワーク側で切り詰めない)."""
    # Arrange
    large_text = "x" * 100_000
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL)
    item = Item(id="item-large", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize(large_text, item)

    # Assert — litellm.completion に渡った user メッセージが切り詰められていない
    messages = mock_completion.call_args.kwargs["messages"]
    user_message = next(m for m in messages if m["role"] == "user")
    assert len(user_message["content"]) == 100_000


def test_llm_summarizer_raises_summarization_error_on_litellm_failure() -> None:
    """litellm が例外を投げた場合、SummarizationError に変換される."""
    # Arrange
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL)
    item = Item(id="item-1", payload=None)

    # Act / Assert
    with (
        patch(_PATCH, side_effect=RuntimeError("API error")),
        pytest.raises(SummarizationError, match="API error"),
    ):
        summarizer.summarize("some text", item)


def test_llm_summarizer_includes_system_prompt_when_set() -> None:
    """system_prompt が設定されている場合、messages の先頭に system ロールで追加される."""
    # Arrange
    summarizer = LLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        system_prompt="You are a helpful assistant.",
    )
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("text", item)

    # Assert
    messages = mock_completion.call_args.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "You are a helpful assistant."}
    assert messages[1]["role"] == "user"


def test_llm_summarizer_omits_system_message_when_empty() -> None:
    """system_prompt が空の場合、system ロールのメッセージは messages に含まれない."""
    # Arrange
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL, system_prompt="")
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("text", item)

    # Assert
    messages = mock_completion.call_args.kwargs["messages"]
    assert all(m["role"] != "system" for m in messages)


def test_llm_summarizer_falls_back_to_empty_string_when_content_is_none() -> None:
    """litellm が content=None を返した場合、Digest.summary は空文字列になる."""
    # Arrange
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL)
    item = Item(id="item-1", payload=None)
    mock_response = MagicMock()
    mock_response.choices[0].message.content = None
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 0

    # Act
    with patch(_PATCH, return_value=mock_response):
        digest = summarizer.summarize("text", item)

    # Assert
    assert digest.summary == ""


def test_llm_summarizer_passes_timeout_to_litellm() -> None:
    """timeout パラメータが litellm.completion へそのまま渡される."""
    # Arrange
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL, timeout=5.0)
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("text", item)

    # Assert
    assert mock_completion.call_args.kwargs["timeout"] == 5.0


def test_llm_summarizer_uses_model_as_full_model_when_slash_present() -> None:
    """model に '/' が含まれる場合、provider を付加せずそのまま litellm へ渡す."""
    # Arrange
    summarizer = LLMSummarizer(provider="openai", model="anthropic/claude-3-haiku")
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("text", item)

    # Assert — provider を重複付加しない
    assert mock_completion.call_args.kwargs["model"] == "anthropic/claude-3-haiku"
