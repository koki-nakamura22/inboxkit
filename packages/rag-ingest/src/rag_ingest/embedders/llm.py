from __future__ import annotations

import logging
import time
from typing import Any, cast

import litellm

from rag_ingest.exceptions import EmbeddingError
from rag_ingest.types import Chunk, Vector

# litellm.embedding has partially-unknown overload types; getattr returns Any,
# avoiding reportUnknownMemberType in pyright strict mode.
_litellm_embedding: Any = getattr(litellm, "embedding")

_logger = logging.getLogger(__name__)


def _extract_prompt_tokens(result: Any) -> int:
    """Safely extract prompt_tokens from a litellm response (dict or object)."""
    usage: Any = None
    if hasattr(result, "get"):
        usage = result.get("usage")
    if usage is None and hasattr(result, "usage"):
        usage = result.usage
    if isinstance(usage, dict):
        prompt_tokens = cast("Any", usage).get("prompt_tokens", 0)
        return int(prompt_tokens or 0)
    if usage is not None:
        return int(getattr(usage, "prompt_tokens", 0) or 0)
    return 0


class LLMEmbedder:
    def __init__(
        self,
        provider: str,
        model: str,
        *,
        batch_size: int = 100,
        timeout: float | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._batch_size = batch_size
        self._timeout = timeout
        self._dim: int | None = None

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    def embed(self, chunks: list[Chunk]) -> list[Vector]:
        vectors: list[Vector] = []
        failed_indices: list[int] = []

        for batch_start in range(0, len(chunks), self._batch_size):
            batch = chunks[batch_start : batch_start + self._batch_size]
            try:
                extra: dict[str, Any] = {}
                if self._timeout is not None:
                    extra["timeout"] = self._timeout
                t0 = time.monotonic()
                result: Any = _litellm_embedding(
                    model=f"{self._provider}/{self._model}",
                    input=[c.text for c in batch],
                    **extra,
                )
                latency_ms = (time.monotonic() - t0) * 1000
                batch_vectors: list[Vector] = [
                    [float(v) for v in item["embedding"]] for item in result["data"]
                ]
                if self._dim is None and batch_vectors:
                    self._dim = len(batch_vectors[0])
                vectors.extend(batch_vectors)
                _logger.info(
                    "embed_completed",
                    extra={
                        "tokens_in": _extract_prompt_tokens(result),
                        "latency_ms": round(latency_ms, 2),
                        "provider": self._provider,
                        "model": self._model,
                        "chunk_count": len(batch),
                    },
                )
            except Exception:
                failed_indices.extend(range(batch_start, batch_start + len(batch)))

        if failed_indices:
            raise EmbeddingError(
                f"Embedding failed for {len(failed_indices)} chunk(s): indices {failed_indices}",
                failed_indices=failed_indices,
            )

        return vectors

    def dim(self) -> int:
        if self._dim is not None:
            return self._dim
        extra: dict[str, Any] = {}
        if self._timeout is not None:
            extra["timeout"] = self._timeout
        result: Any = _litellm_embedding(
            model=f"{self._provider}/{self._model}",
            input=[""],
            **extra,
        )
        self._dim = len(result["data"][0]["embedding"])
        return self._dim
