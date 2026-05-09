from __future__ import annotations

import time
from typing import Any, ClassVar

import litellm
from dotenv import load_dotenv

from ..logging import get_logger
from ..types import Digest, DigestkitError, Item

load_dotenv()

log = get_logger(__name__)


class SummarizationError(DigestkitError):
    """LLM 呼び出しの非リカバラブル失敗."""


class LLMSummarizer:
    """LiteLLM 経由で 1 アイテム 1 要約を返す Summarizer.

    要約の長さ (length) を以下の 3 通りで制御できる:

    1. ``user_prompt_template`` のみ指定 (旧 API)
       単一テンプレートを使う。``length`` 引数は無視される。
    2. ``prompts`` mapping を指定 (新 API)
       ``{"short": ..., "standard": ..., "detailed": ...}`` のような段階別
       テンプレートを保持し、``default_length`` または ``summarize(..., length=)``
       で実行時に選択。利用者は段階数を任意に決められる。
    3. どちらも未指定
       完全に旧 API 互換 (``"{text}"`` を単発で投入)。

    digestkit のビルトインデフォルト 3 段階プロンプトは
    :pyattr:`LLMSummarizer.DEFAULT_PROMPTS` で公開しており、利用者は
    ``LLMSummarizer(provider=..., model=..., prompts=LLMSummarizer.DEFAULT_PROMPTS)``
    の 1 行で length 機能を有効化できる。
    """

    #: 人間向け要約の標準的な 3 段階プロンプト.
    #: 利用者は ``prompts=LLMSummarizer.DEFAULT_PROMPTS`` で opt-in する.
    DEFAULT_PROMPTS: ClassVar[dict[str, str]] = {
        "short": (
            "次のドキュメントを 3 行以内で日本語要約してください。"
            "重要キーワードを残し、装飾は不要です。\n\n{text}"
        ),
        "standard": (
            "次のドキュメントを日本語で簡潔に要約してください。"
            "段落は 2〜3 つに収めてください。\n\n{text}"
        ),
        "detailed": (
            "次のドキュメントを日本語で章立て要約してください。"
            "主要な論点・根拠・数値を保持し、見出し付きの構造で整理してください。\n\n{text}"
        ),
    }

    def __init__(
        self,
        provider: str,
        model: str,
        system_prompt: str = "",
        user_prompt_template: str | None = None,
        *,
        prompts: dict[str, str] | None = None,
        default_length: str = "standard",
        timeout: float | None = None,
    ) -> None:
        if user_prompt_template is not None and prompts is not None:
            raise ValueError(
                "user_prompt_template と prompts は同時に指定できません。"
                "段階別要約を使う場合は prompts のみ指定してください"
            )
        if prompts is not None:
            if not prompts:
                raise ValueError("prompts は 1 つ以上のテンプレートを含む必要があります")
            if default_length not in prompts:
                raise ValueError(
                    f"default_length={default_length!r} が prompts のキー "
                    f"{sorted(prompts)} に含まれていません"
                )

        self._provider = provider
        self._model = model
        self._system_prompt = system_prompt
        # 旧 API 互換: どちらも未指定なら "{text}" 単発モード.
        self._user_prompt_template: str | None = (
            user_prompt_template if user_prompt_template is not None or prompts is None else None
        )
        if user_prompt_template is None and prompts is None:
            self._user_prompt_template = "{text}"
        self._prompts: dict[str, str] | None = dict(prompts) if prompts else None
        self._default_length = default_length
        self._timeout = timeout

    def _resolve_template(self, length: str | None) -> str:
        """length 引数を踏まえて使用するテンプレートを 1 つ返す."""
        # 旧 API 単発モード: length は無視 (互換性最優先)
        if self._prompts is None:
            assert self._user_prompt_template is not None  # __init__ で担保
            if length is not None:
                log.debug(
                    "ignoring length=%r because user_prompt_template is in single-template mode",
                    length,
                )
            return self._user_prompt_template

        # 段階別モード
        chosen = length if length is not None else self._default_length
        if chosen not in self._prompts:
            raise ValueError(
                f"length={chosen!r} は prompts のキー {sorted(self._prompts)} に含まれていません"
            )
        return self._prompts[chosen]

    def summarize(self, text: str, item: Item, *, length: str | None = None) -> Digest:
        full_model = f"{self._provider}/{self._model}" if "/" not in self._model else self._model
        template = self._resolve_template(length)
        user_prompt = template.format(text=text, item=item)
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        start = time.perf_counter()
        try:
            response: Any = litellm.completion(  # type: ignore[reportUnknownMemberType]
                model=full_model, messages=messages, timeout=self._timeout
            )
        except Exception as e:
            raise SummarizationError(str(e)) from e
        latency_ms = int((time.perf_counter() - start) * 1000)

        summary: str = response.choices[0].message.content or ""
        usage: Any = response.usage
        digest = Digest(
            summary=summary,
            tokens_in=getattr(usage, "prompt_tokens", 0),
            tokens_out=getattr(usage, "completion_tokens", 0),
            latency_ms=latency_ms,
            model=full_model,
        )
        log.info(
            "llm_call_completed",
            extra={
                "tokens_in": digest.tokens_in,
                "tokens_out": digest.tokens_out,
                "latency_ms": digest.latency_ms,
                "provider": self._provider,
                "model": self._model,
            },
        )
        return digest
