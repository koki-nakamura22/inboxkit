"""ChunkedLLMSummarizer (LiteLLM mock).

実装ファイル: packages/digestkit/src/digestkit/summarizers/chunked.py
ADR: docs/packages/digestkit/adr/0001-chunked-summarizer-as-separate-class.md
Issue: #11
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from digestkit.summarizers.chunked import ChunkedLLMSummarizer
from digestkit.summarizers.llm import SummarizationError
from digestkit.types import Item

_PROVIDER = "openai"
_MODEL = "gpt-4"
_FULL_MODEL = f"{_PROVIDER}/{_MODEL}"
_PATCH_COMPLETION = "digestkit.summarizers.chunked.litellm.completion"
_PATCH_TOKEN_COUNTER = "digestkit.summarizers.chunked.litellm.token_counter"
_PATCH_GET_MODEL_INFO = "digestkit.summarizers.chunked.litellm.get_model_info"


def _mock_response(content: str = "OK", in_tokens: int = 10, out_tokens: int = 5) -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = content
    mock.usage.prompt_tokens = in_tokens
    mock.usage.completion_tokens = out_tokens
    return mock


# --------------------------------------------------------------------- ctor 検証


def test_chunk_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, chunk_size=0)


def test_chunk_overlap_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, chunk_overlap=-1)


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, chunk_size=100, chunk_overlap=100)


def test_map_prompt_requires_text_placeholder() -> None:
    with pytest.raises(ValueError, match="map_prompt"):
        ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, map_prompt="no placeholder")


def test_reduce_prompt_requires_text_placeholder() -> None:
    with pytest.raises(ValueError, match="reduce_prompt"):
        ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, reduce_prompt="no placeholder")


def test_default_length_must_exist_in_prompts() -> None:
    with pytest.raises(ValueError, match="含まれていません"):
        ChunkedLLMSummarizer(
            provider=_PROVIDER,
            model=_MODEL,
            prompts={"short": "{text}"},
            default_length="standard",
        )


# ----------------------------------------------------------- short-text fallback


def test_short_text_uses_single_shot_with_reduce_prompt() -> None:
    """総トークンが threshold 以下なら map/reduce を経由せず単発 (reduce_prompt) で返す."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER, model=_MODEL, chunk_size=1000, reserve_tokens=0
    )
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response("ANSWER")) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=50),
    ):
        digest = summarizer.summarize("short text", item)

    mock_completion.assert_called_once()
    assert digest.summary == "ANSWER"
    # 単発呼び出しなので reduce_prompt を含む user メッセージ
    msg = mock_completion.call_args.kwargs["messages"][0]
    assert msg["role"] == "user"
    assert "short text" in msg["content"]
    assert "統合" in msg["content"]  # reduce_prompt 由来


def test_short_text_with_prompts_uses_length_template() -> None:
    """prompts 指定 + 短文時、最終テンプレートとして prompts[length] が使われる."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        chunk_size=1000,
        reserve_tokens=0,
        prompts={"short": "SHORT: {text}", "standard": "STANDARD: {text}"},
        default_length="standard",
    )
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response("OUT")) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=10),
    ):
        summarizer.summarize("hello", item, length="short")

    msg = mock_completion.call_args.kwargs["messages"][0]
    assert msg["content"] == "SHORT: hello"


# --------------------------------------------------------------- map-reduce 経路


def test_long_text_triggers_map_reduce() -> None:
    """総トークンが threshold 超なら chunk 分割 → map → 最終 reduce が呼ばれる."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER, model=_MODEL, chunk_size=100, reserve_tokens=0
    )
    item = Item(id="i", payload=None)

    # 段落 3 つ. token_counter は文字数で近似してチャンクが 3 に分かれるよう設計.
    text = (
        ("para1 " * 40).strip()
        + "\n\n"
        + ("para2 " * 40).strip()
        + "\n\n"
        + ("para3 " * 40).strip()
    )

    def fake_count(*, model: str, text: str) -> int:
        return len(text)

    # 各 LLM 呼び出しはユニークな出力を返す
    responses = [_mock_response(f"part{i}", in_tokens=5, out_tokens=3) for i in range(10)]

    with (
        patch(_PATCH_COMPLETION, side_effect=responses) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, side_effect=fake_count),
    ):
        digest = summarizer.summarize(text, item)

    # map (3 チャンク) + 最終 reduce (1) = 4 回呼ばれる想定
    # ただし chunk_size=100 を文字基準で見るため境界次第で分割数は 2〜3.
    # 最低: 2 chunk + 1 reduce = 3
    assert mock_completion.call_count >= 3
    # 最後の呼び出しが reduce で、partial summaries を結合したテキストを含む
    last_msg = mock_completion.call_args.kwargs["messages"][0]["content"]
    assert "part0" in last_msg
    # 戻り値の summary は最後のレスポンス (= 最終 reduce) のもの
    assert digest.summary.startswith("part")


def test_long_text_aggregates_token_counts_across_calls() -> None:
    """tokens_in / tokens_out / latency_ms は map + reduce の合算."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER, model=_MODEL, chunk_size=50, reserve_tokens=0
    )
    item = Item(id="i", payload=None)
    text = "a" * 200 + "\n\n" + "b" * 200

    def fake_count(*, model: str, text: str) -> int:
        return len(text)

    responses = [_mock_response(f"r{i}", in_tokens=10, out_tokens=4) for i in range(10)]

    with (
        patch(_PATCH_COMPLETION, side_effect=responses) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, side_effect=fake_count),
    ):
        digest = summarizer.summarize(text, item)

    n_calls = mock_completion.call_count
    assert digest.tokens_in == 10 * n_calls
    assert digest.tokens_out == 4 * n_calls
    assert digest.model == _FULL_MODEL


def test_long_text_with_prompts_applies_length_only_at_final_reduce() -> None:
    """中間 reduce は中立 reduce_prompt、最終 reduce のみ prompts[length] を使う."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        chunk_size=50,
        reserve_tokens=0,
        prompts={"short": "FINAL_SHORT: {text}", "standard": "FINAL_STD: {text}"},
        default_length="standard",
    )
    item = Item(id="i", payload=None)
    text = "x" * 150 + "\n\n" + "y" * 150

    def fake_count(*, model: str, text: str) -> int:
        return len(text)

    responses = [_mock_response(f"p{i}") for i in range(10)]

    with (
        patch(_PATCH_COMPLETION, side_effect=responses) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, side_effect=fake_count),
    ):
        summarizer.summarize(text, item, length="short")

    # 最後の呼び出しが最終 reduce で、FINAL_SHORT プレフィックスを持つ
    last_call_msg = mock_completion.call_args.kwargs["messages"][0]["content"]
    assert last_call_msg.startswith("FINAL_SHORT:")
    # それ以外の呼び出しは map_prompt または reduce_prompt (= "FINAL_SHORT" を含まない)
    earlier_msgs = [c.kwargs["messages"][0]["content"] for c in mock_completion.call_args_list[:-1]]
    assert all(not m.startswith("FINAL_SHORT:") for m in earlier_msgs)


# ------------------------------------------------------------------ 失敗時挙動


def test_chunk_failure_raises_summarization_error_with_index() -> None:
    """1 チャンク失敗で fail-fast、エラーメッセージにチャンク index を含む."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER, model=_MODEL, chunk_size=50, reserve_tokens=0
    )
    item = Item(id="i", payload=None)
    text = "a" * 100 + "\n\n" + "b" * 100

    def fake_count(*, model: str, text: str) -> int:
        return len(text)

    def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
        raise RuntimeError("boom")

    with (
        patch(_PATCH_COMPLETION, side_effect=side_effect),
        patch(_PATCH_TOKEN_COUNTER, side_effect=fake_count),
        pytest.raises(SummarizationError, match=r"chunk 0/\d+"),
    ):
        summarizer.summarize(text, item)


# ------------------------------------------------------------------ 設定派生


def test_chunk_size_falls_back_to_max_input_tokens_minus_reserve() -> None:
    """chunk_size 未指定なら max_input_tokens (= 入力 context window) - reserve_tokens を使う.

    Regression: #23. 以前は litellm.get_max_tokens (= 出力上限) を読んでいたため、
    1M context window のモデルでも 57k tokens で chunked 経路に突入していた.
    """
    summarizer = ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, reserve_tokens=1000)
    item = Item(id="i", payload=None)

    # max_input_tokens=5000 → threshold=4000. 入力が 3999 トークンなら単発 fallback.
    # max_tokens=2000 (= 出力上限) を返しても、こちらは無視されるべき.
    info = {"max_input_tokens": 5000, "max_tokens": 2000, "max_output_tokens": 2000}
    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response("OUT")) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=3999),
        patch(_PATCH_GET_MODEL_INFO, return_value=info),
    ):
        summarizer.summarize("text", item)

    mock_completion.assert_called_once()


def test_chunk_size_falls_back_to_max_tokens_when_max_input_tokens_missing() -> None:
    """max_input_tokens を公開していない古いバックエンドでは max_tokens にフォールバック."""
    summarizer = ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, reserve_tokens=1000)
    item = Item(id="i", payload=None)

    # max_input_tokens が無い → max_tokens=5000 が採用され threshold=4000.
    info: dict[str, Any] = {"max_tokens": 5000}
    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response("OUT")) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=3999),
        patch(_PATCH_GET_MODEL_INFO, return_value=info),
    ):
        summarizer.summarize("text", item)

    mock_completion.assert_called_once()


def test_chunk_size_does_not_use_output_limit_for_context_window() -> None:
    """gemini-2.5-flash 風: max_input_tokens=1M, max_tokens=65k のとき 1M を採用する.

    Regression: #23. 修正前は max_tokens (= 65k) を採用してしまっていた.
    """
    summarizer = ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, reserve_tokens=8000)
    item = Item(id="i", payload=None)

    info = {
        "max_input_tokens": 1_048_576,
        "max_tokens": 65_535,
        "max_output_tokens": 65_535,
    }
    # 185k tokens の入力. max_tokens (=65535) ベースだと chunked 経路、
    # max_input_tokens (=1M) ベースなら単発 fallback (185k < 1M - 8000 = 1,040,576).
    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response("OUT")) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=185_000),
        patch(_PATCH_GET_MODEL_INFO, return_value=info),
    ):
        summarizer.summarize("text", item)

    # 単発呼び出しで完了することを保証 (= context window を取り違えていない).
    mock_completion.assert_called_once()


def test_unknown_model_max_tokens_uses_8000_default() -> None:
    """get_model_info が例外でも fallback 8000 で動く."""
    summarizer = ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, reserve_tokens=0)
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response("OUT")) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=100),
        patch(_PATCH_GET_MODEL_INFO, side_effect=RuntimeError("unknown model")),
    ):
        summarizer.summarize("text", item)

    mock_completion.assert_called_once()


def test_token_counter_failure_falls_back_to_char_estimate() -> None:
    """litellm.token_counter が例外なら文字数 / 4 で近似してそのまま動く."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER, model=_MODEL, chunk_size=10_000, reserve_tokens=0
    )
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response("OUT")) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, side_effect=RuntimeError("no tokenizer")),
    ):
        digest = summarizer.summarize("hello world", item)

    mock_completion.assert_called_once()
    assert digest.summary == "OUT"


# ---------------------------------------------------------------- system prompt


def test_system_prompt_propagates_to_each_call() -> None:
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER,
        model=_MODEL,
        chunk_size=1000,
        reserve_tokens=0,
        system_prompt="You are precise.",
    )
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response()) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=10),
    ):
        summarizer.summarize("text", item)

    msgs = mock_completion.call_args.kwargs["messages"]
    assert msgs[0] == {"role": "system", "content": "You are precise."}


# --------------------------------------------------------------- model resolution


def test_model_with_slash_is_passed_through() -> None:
    summarizer = ChunkedLLMSummarizer(
        provider="openai", model="anthropic/claude-3-haiku", chunk_size=1000, reserve_tokens=0
    )
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response()) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=10),
    ):
        summarizer.summarize("text", item)

    assert mock_completion.call_args.kwargs["model"] == "anthropic/claude-3-haiku"


def test_default_prompts_classvar_mirrors_llmsummarizer() -> None:
    from digestkit.summarizers.llm import LLMSummarizer

    assert ChunkedLLMSummarizer.DEFAULT_PROMPTS is LLMSummarizer.DEFAULT_PROMPTS


# ----------------------------------------------------------------- num_retries (#24)


def test_chunked_default_num_retries_is_zero() -> None:
    """デフォルトでは num_retries=0 が litellm へ渡る (Issue #24)."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER, model=_MODEL, chunk_size=1000, reserve_tokens=0
    )
    item = Item(id="i", payload=None)

    with (
        patch(_PATCH_COMPLETION, return_value=_mock_response()) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, return_value=10),
    ):
        summarizer.summarize("text", item)

    assert mock_completion.call_args.kwargs["num_retries"] == 0


def test_chunked_passes_num_retries_to_litellm_on_each_chunk() -> None:
    """map / reduce 全 chunk 呼び出しで num_retries が litellm へ伝播する (Issue #24)."""
    summarizer = ChunkedLLMSummarizer(
        provider=_PROVIDER, model=_MODEL, chunk_size=100, reserve_tokens=0, num_retries=2
    )
    item = Item(id="i", payload=None)

    text = ("para1 " * 40).strip() + "\n\n" + ("para2 " * 40).strip()

    def fake_count(*, model: str, text: str) -> int:
        # 2 段落でそれぞれ chunk_size 以下、結合すると超える形
        return len(text) // 2

    with (
        patch(
            _PATCH_COMPLETION, return_value=_mock_response("OUT", out_tokens=1)
        ) as mock_completion,
        patch(_PATCH_TOKEN_COUNTER, side_effect=fake_count),
    ):
        summarizer.summarize(text, item)

    assert mock_completion.call_count >= 2
    for call in mock_completion.call_args_list:
        assert call.kwargs["num_retries"] == 2


def test_chunked_rejects_negative_num_retries() -> None:
    """num_retries に負値を渡すと ValueError (Issue #24)."""
    with pytest.raises(ValueError, match="num_retries"):
        ChunkedLLMSummarizer(provider=_PROVIDER, model=_MODEL, num_retries=-1)
