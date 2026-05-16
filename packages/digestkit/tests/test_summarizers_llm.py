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


def test_llm_summarizer_default_num_retries_is_zero() -> None:
    """デフォルトでは num_retries=0 が litellm へ渡る (旧挙動維持, Issue #24)."""
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL)
    item = Item(id="item-1", payload=None)

    with patch(_PATCH, return_value=_make_mock_response()) as mock_completion:
        summarizer.summarize("text", item)

    assert mock_completion.call_args.kwargs["num_retries"] == 0


def test_llm_summarizer_passes_num_retries_to_litellm() -> None:
    """num_retries パラメータが litellm.completion へそのまま渡される (Issue #24)."""
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL, num_retries=3)
    item = Item(id="item-1", payload=None)

    with patch(_PATCH, return_value=_make_mock_response()) as mock_completion:
        summarizer.summarize("text", item)

    assert mock_completion.call_args.kwargs["num_retries"] == 3


def test_llm_summarizer_rejects_negative_num_retries() -> None:
    """num_retries に負値を渡すと ValueError (Issue #24)."""
    with pytest.raises(ValueError, match="num_retries"):
        LLMSummarizer(provider=_PROVIDER, model=_MODEL, num_retries=-1)


def test_prompts_and_user_prompt_template_are_mutually_exclusive() -> None:
    """user_prompt_template と prompts の同時指定は ValueError を投げる."""
    with pytest.raises(ValueError, match="同時に指定できません"):
        LLMSummarizer(
            provider=_PROVIDER,
            model=_MODEL,
            user_prompt_template="x: {text}",
            prompts={"standard": "y: {text}"},
        )


def test_prompts_empty_mapping_rejected() -> None:
    """空の prompts 指定は ValueError."""
    with pytest.raises(ValueError, match="1 つ以上"):
        LLMSummarizer(provider=_PROVIDER, model=_MODEL, prompts={})


def test_prompts_default_length_must_exist_in_mapping() -> None:
    """default_length が prompts に無いキーの場合は ValueError."""
    with pytest.raises(ValueError, match="含まれていません"):
        LLMSummarizer(
            provider=_PROVIDER,
            model=_MODEL,
            prompts={"short": "s: {text}"},
            default_length="standard",
        )


def test_prompts_uses_default_length_when_summarize_omits_length() -> None:
    """summarize() で length 未指定なら default_length のテンプレートが選ばれる."""
    summarizer = LLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        prompts={
            "short": "SHORT: {text}",
            "standard": "STANDARD: {text}",
            "detailed": "DETAILED: {text}",
        },
        default_length="detailed",
    )
    item = Item(id="i", payload=None)
    mock_response = _make_mock_response()

    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("hi", item)

    user_msg = next(m for m in mock_completion.call_args.kwargs["messages"] if m["role"] == "user")
    assert user_msg["content"] == "DETAILED: hi"


def test_prompts_runtime_length_overrides_default() -> None:
    """summarize(length=...) は default_length より優先される."""
    summarizer = LLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        prompts={
            "short": "SHORT: {text}",
            "standard": "STANDARD: {text}",
        },
        default_length="standard",
    )
    item = Item(id="i", payload=None)
    mock_response = _make_mock_response()

    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("hi", item, length="short")

    user_msg = next(m for m in mock_completion.call_args.kwargs["messages"] if m["role"] == "user")
    assert user_msg["content"] == "SHORT: hi"


def test_prompts_unknown_length_at_runtime_raises() -> None:
    """summarize(length=) が prompts に無いキーの場合は ValueError."""
    summarizer = LLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        prompts={"short": "s: {text}"},
        default_length="short",
    )
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH, return_value=_make_mock_response()),
        pytest.raises(ValueError, match="含まれていません"),
    ):
        summarizer.summarize("hi", item, length="detailed")


def test_user_prompt_template_mode_ignores_length_arg() -> None:
    """旧 API (user_prompt_template) モードでは length 引数を黙って無視する."""
    summarizer = LLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        user_prompt_template="LEGACY: {text}",
    )
    item = Item(id="i", payload=None)
    mock_response = _make_mock_response()

    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("hi", item, length="detailed")

    user_msg = next(m for m in mock_completion.call_args.kwargs["messages"] if m["role"] == "user")
    assert user_msg["content"] == "LEGACY: hi"


def test_default_prompts_class_var_has_three_levels() -> None:
    """ビルトイン DEFAULT_PROMPTS は短/中/詳の 3 段階を提供する."""
    assert set(LLMSummarizer.DEFAULT_PROMPTS.keys()) == {"short", "standard", "detailed"}
    for tmpl in LLMSummarizer.DEFAULT_PROMPTS.values():
        assert "{text}" in tmpl


def test_default_prompts_can_be_used_by_reference() -> None:
    """``prompts=LLMSummarizer.DEFAULT_PROMPTS`` の opt-in 経路が動作する."""
    summarizer = LLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        prompts=LLMSummarizer.DEFAULT_PROMPTS,
    )
    item = Item(id="i", payload=None)
    mock_response = _make_mock_response()

    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("hello", item, length="short")

    user_msg = next(m for m in mock_completion.call_args.kwargs["messages"] if m["role"] == "user")
    # short プロンプトのプレフィックスが含まれ、{text} 部分に "hello" が入る
    assert "3 行以内" in user_msg["content"]
    assert "hello" in user_msg["content"]


def test_llm_summarizer_accepts_system_prompt_as_content_blocks_for_cache_control() -> None:
    """system_prompt に content block のリストを渡すと cache_control もそのまま渡る (Issue #39)."""
    # Arrange
    system_blocks = [
        {
            "type": "text",
            "text": "<長い system prompt>",
            "cache_control": {"type": "ephemeral"},
        },
    ]
    summarizer = LLMSummarizer(
        provider="anthropic",
        model="claude-sonnet-4-6",
        system_prompt=system_blocks,
    )
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    # Act
    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("text", item)

    # Assert
    messages = mock_completion.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == system_blocks
    # 念のため cache_control が落とされていないことを明示的に検証
    assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert messages[1]["role"] == "user"


def test_llm_summarizer_omits_system_message_when_blocks_list_is_empty() -> None:
    """system_prompt に空 list を渡した場合は system メッセージを生成しない (str='' と同等)."""
    summarizer = LLMSummarizer(provider=_PROVIDER, model=_MODEL, system_prompt=[])
    item = Item(id="item-1", payload=None)
    mock_response = _make_mock_response()

    with patch(_PATCH, return_value=mock_response) as mock_completion:
        summarizer.summarize("text", item)

    messages = mock_completion.call_args.kwargs["messages"]
    assert all(m["role"] != "system" for m in messages)


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
