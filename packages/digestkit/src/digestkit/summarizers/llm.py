from __future__ import annotations

import time
from typing import Any

import litellm
from dotenv import load_dotenv

from ..types import Digest, DigestkitError, Item

load_dotenv()


class SummarizationError(DigestkitError):
    """LLM 呼び出しの非リカバラブル失敗."""


class LLMSummarizer:
    def __init__(
        self,
        provider: str,
        model: str,
        system_prompt: str = "",
        user_prompt_template: str = "{text}",
        timeout: float | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._system_prompt = system_prompt
        self._user_prompt_template = user_prompt_template
        self._timeout = timeout

    def summarize(self, text: str, item: Item) -> Digest:
        full_model = f"{self._provider}/{self._model}" if "/" not in self._model else self._model
        user_prompt = self._user_prompt_template.format(text=text, item=item)
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
        return Digest(
            summary=summary,
            tokens_in=getattr(usage, "prompt_tokens", 0),
            tokens_out=getattr(usage, "completion_tokens", 0),
            latency_ms=latency_ms,
            model=full_model,
        )
