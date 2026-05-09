"""AC-003 / AC-003a / AC-003b: LLMSummarizer (LiteLLM mock)

実装ファイル: packages/digestkit/src/digestkit/summarizers/llm.py
対応 SR: SR-F-003
Fixtures: tests/fixtures/litellm/completion_basic.json
"""

from __future__ import annotations

import pytest


def test_llm_summarizer_calls_litellm_with_expanded_prompt() -> None:
    """AC-003: user_prompt_template の {text} 展開後に litellm.completion へ渡される."""
    pytest.fail("not yet implemented")


def test_llm_summarizer_returns_digest_with_metadata() -> None:
    """AC-003: 戻り値 Digest に summary / tokens_in / tokens_out / latency_ms / model が記録."""
    pytest.fail("not yet implemented")


def test_llm_summarizer_handles_empty_text_input() -> None:
    """AC-003a: 空文字入力で例外を投げず LiteLLM 呼び出し成功."""
    pytest.fail("not yet implemented")


def test_llm_summarizer_passes_large_text_without_truncation() -> None:
    """AC-003b: 100,000 文字入力をそのまま LiteLLM へ渡す (フレームワーク側で切り詰めない)."""
    pytest.fail("not yet implemented")
