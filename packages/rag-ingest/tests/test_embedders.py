"""AC-004 / AC-004b / AC-R-001: LLMEmbedder — batch split, required args, failure handling."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from rag_ingest.embedders import LLMEmbedder
from rag_ingest.exceptions import EmbeddingError, RagIngestError
from rag_ingest.protocols import Embedder
from rag_ingest.types import Chunk

_PATCH = "rag_ingest.embedders.llm._litellm_embedding"


def _chunk(i: int) -> Chunk:
    return Chunk(text=f"chunk text {i}", chunk_index=i)


def _mock_response(dim: int, count: int) -> dict[str, Any]:
    return {"data": [{"embedding": [0.0] * dim} for _ in range(count)]}


# ── AC-004: batch split ────────────────────────────────────────────────────────


def test_batch_split_calls_litellm_twice_for_100_chunks_batch_50() -> None:
    # Arrange
    chunks = [_chunk(i) for i in range(100)]
    mock_resp = _mock_response(dim=1024, count=50)

    # Act
    with patch(_PATCH, return_value=mock_resp) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=50)
        vectors = embedder.embed(chunks)

    # Assert
    assert m.call_count == 2
    assert len(vectors) == 100


def test_batch_split_dim_cached_from_first_batch() -> None:
    # Arrange
    chunks = [_chunk(i) for i in range(100)]
    mock_resp = _mock_response(dim=1024, count=50)

    # Act
    with patch(_PATCH, return_value=mock_resp):
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=50)
        embedder.embed(chunks)

    # Assert — dim is cached after embed, no extra litellm call needed
    with patch(_PATCH) as m:
        assert embedder.dim() == 1024
    m.assert_not_called()


def test_batch_split_vectors_have_correct_dimension() -> None:
    # Arrange
    chunks = [_chunk(i) for i in range(100)]
    mock_resp = _mock_response(dim=512, count=50)

    # Act
    with patch(_PATCH, return_value=mock_resp):
        embedder = LLMEmbedder(provider="openai", model="text-embedding-3-small", batch_size=50)
        vectors = embedder.embed(chunks)

    # Assert — every vector has the correct dimension
    assert all(len(v) == 512 for v in vectors)


def test_single_batch_no_split_for_chunks_below_limit() -> None:
    # Arrange
    chunks = [_chunk(i) for i in range(10)]
    mock_resp = _mock_response(dim=256, count=10)

    # Act
    with patch(_PATCH, return_value=mock_resp) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=100)
        vectors = embedder.embed(chunks)

    # Assert
    assert m.call_count == 1
    assert len(vectors) == 10


def test_batch_split_exact_boundary_calls_twice() -> None:
    # Arrange: 6 chunks, batch_size=3 → exactly 2 batches
    chunks = [_chunk(i) for i in range(6)]

    # Act
    with patch(_PATCH, return_value=_mock_response(dim=4, count=3)) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=3)
        vectors = embedder.embed(chunks)

    # Assert
    assert m.call_count == 2
    assert len(vectors) == 6


def test_batch_split_uneven_remainder_produces_correct_count() -> None:
    # Arrange: 7 chunks, batch_size=3 → batches of [3, 3, 1]
    chunks = [_chunk(i) for i in range(7)]
    call_count = 0

    def side_effect(**kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        n = len(kwargs["input"])
        return _mock_response(dim=4, count=n)

    # Act
    with patch(_PATCH, side_effect=side_effect):
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=3)
        vectors = embedder.embed(chunks)

    # Assert
    assert call_count == 3
    assert len(vectors) == 7


def test_embed_uses_provider_slash_model_format() -> None:
    # Arrange
    chunks = [_chunk(0)]
    mock_resp = _mock_response(dim=4, count=1)

    # Act
    with patch(_PATCH, return_value=mock_resp) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3")
        embedder.embed(chunks)

    # Assert — litellm receives "provider/model" as the model string
    assert m.call_args.kwargs["model"] == "voyage/voyage-3"


def test_embed_passes_chunk_texts_as_input() -> None:
    # Arrange
    chunks = [Chunk(text="hello", chunk_index=0), Chunk(text="world", chunk_index=1)]
    mock_resp = _mock_response(dim=4, count=2)

    # Act
    with patch(_PATCH, return_value=mock_resp) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3")
        embedder.embed(chunks)

    # Assert
    assert m.call_args.kwargs["input"] == ["hello", "world"]


def test_embed_empty_chunks_returns_empty_list() -> None:
    # Arrange / Act
    with patch(_PATCH) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3")
        vectors = embedder.embed([])

    # Assert
    assert vectors == []
    m.assert_not_called()


# ── AC-004b: provider / model 必須引数 ────────────────────────────────────────


def test_llmembedder_requires_both_provider_and_model() -> None:
    with pytest.raises(TypeError):
        LLMEmbedder()  # type: ignore[call-arg]


def test_llmembedder_requires_provider() -> None:
    with pytest.raises(TypeError):
        LLMEmbedder(model="voyage-3")  # type: ignore[call-arg]


def test_llmembedder_requires_model() -> None:
    with pytest.raises(TypeError):
        LLMEmbedder(provider="voyage")  # type: ignore[call-arg]


# ── AC-R-001: embed failure raises EmbeddingError with failed indices ──────────


def test_all_batches_fail_raises_embedding_error_with_all_indices() -> None:
    # Arrange
    chunks = [_chunk(i) for i in range(5)]

    # Act / Assert
    with patch(_PATCH, side_effect=RuntimeError("API error")):
        embedder = LLMEmbedder(provider="voyage", model="voyage-3")
        with pytest.raises(EmbeddingError) as exc_info:
            embedder.embed(chunks)

    assert exc_info.value.failed_indices == list(range(5))


def test_second_batch_failure_includes_correct_failed_indices() -> None:
    # Arrange: 10 chunks, batch_size=5; first batch succeeds, second fails
    chunks = [_chunk(i) for i in range(10)]
    call_n = 0

    def side_effect(**kwargs: Any) -> Any:
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _mock_response(dim=4, count=5)
        raise RuntimeError("second batch failed")

    # Act / Assert
    with patch(_PATCH, side_effect=side_effect):
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=5)
        with pytest.raises(EmbeddingError) as exc_info:
            embedder.embed(chunks)

    assert exc_info.value.failed_indices == list(range(5, 10))


def test_first_batch_failure_includes_correct_failed_indices() -> None:
    # Arrange: 6 chunks, batch_size=3; first batch fails, second succeeds
    chunks = [_chunk(i) for i in range(6)]
    call_n = 0

    def side_effect(**kwargs: Any) -> Any:
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            raise RuntimeError("first batch failed")
        return _mock_response(dim=4, count=3)

    # Act / Assert
    with patch(_PATCH, side_effect=side_effect):
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=3)
        with pytest.raises(EmbeddingError) as exc_info:
            embedder.embed(chunks)

    assert exc_info.value.failed_indices == list(range(3))


def test_embedding_error_is_rag_ingest_error_subclass() -> None:
    # Arrange
    chunks = [_chunk(0)]

    # Act / Assert
    with patch(_PATCH, side_effect=RuntimeError("err")):
        embedder = LLMEmbedder(provider="voyage", model="voyage-3")
        with pytest.raises(EmbeddingError) as exc_info:
            embedder.embed(chunks)

    assert isinstance(exc_info.value, RagIngestError)


# ── provider / model properties ───────────────────────────────────────────────


def test_provider_property_returns_constructor_value() -> None:
    embedder = LLMEmbedder(provider="voyage", model="voyage-3")
    assert embedder.provider == "voyage"


def test_model_property_returns_constructor_value() -> None:
    embedder = LLMEmbedder(provider="voyage", model="voyage-3")
    assert embedder.model == "voyage-3"


def test_provider_and_model_are_independent_per_instance() -> None:
    a = LLMEmbedder(provider="voyage", model="voyage-3")
    b = LLMEmbedder(provider="openai", model="text-embedding-3-small")
    assert a.provider == "voyage"
    assert b.provider == "openai"
    assert a.model == "voyage-3"
    assert b.model == "text-embedding-3-small"


# ── dim() caching ──────────────────────────────────────────────────────────────


def test_dim_returns_cached_value_after_embed_without_extra_call() -> None:
    # Arrange
    chunks = [_chunk(i) for i in range(3)]
    with patch(_PATCH, return_value=_mock_response(dim=768, count=3)):
        embedder = LLMEmbedder(provider="openai", model="text-embedding-3-small")
        embedder.embed(chunks)

    # Act — dim() must not call litellm again
    with patch(_PATCH) as m:
        dim = embedder.dim()

    # Assert
    assert dim == 768
    m.assert_not_called()


def test_dim_probes_litellm_when_called_before_embed() -> None:
    # Arrange
    embedder = LLMEmbedder(provider="voyage", model="voyage-3")
    probe_resp = _mock_response(dim=1024, count=1)

    # Act
    with patch(_PATCH, return_value=probe_resp) as m:
        dim = embedder.dim()

    # Assert
    assert dim == 1024
    m.assert_called_once()


def test_dim_cached_after_probe_no_second_call() -> None:
    # Arrange
    embedder = LLMEmbedder(provider="voyage", model="voyage-3")
    with patch(_PATCH, return_value=_mock_response(dim=512, count=1)):
        embedder.dim()  # first call triggers probe

    # Act — second dim() must not call litellm
    with patch(_PATCH) as m:
        dim = embedder.dim()

    # Assert
    assert dim == 512
    m.assert_not_called()


# ── timeout parameter ──────────────────────────────────────────────────────────


def test_timeout_none_does_not_add_timeout_kwarg() -> None:
    # Arrange: when timeout is None we skip adding it (use litellm default)
    chunks = [_chunk(0)]
    mock_resp = _mock_response(dim=4, count=1)

    # Act
    with patch(_PATCH, return_value=mock_resp) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", timeout=None)
        embedder.embed(chunks)

    # Assert
    assert "timeout" not in m.call_args.kwargs


def test_timeout_value_forwarded_to_litellm() -> None:
    # Arrange
    chunks = [_chunk(0)]
    mock_resp = _mock_response(dim=4, count=1)

    # Act
    with patch(_PATCH, return_value=mock_resp) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", timeout=30.0)
        embedder.embed(chunks)

    # Assert
    assert m.call_args.kwargs["timeout"] == 30.0


def test_batch_size_one_calls_litellm_once_per_chunk() -> None:
    # Arrange: batch_size=1 is the minimum — every chunk is its own batch
    chunks = [_chunk(i) for i in range(3)]

    def side_effect(**kwargs: Any) -> Any:
        n = len(kwargs["input"])
        return _mock_response(dim=4, count=n)

    # Act
    with patch(_PATCH, side_effect=side_effect) as m:
        embedder = LLMEmbedder(provider="voyage", model="voyage-3", batch_size=1)
        vectors = embedder.embed(chunks)

    # Assert
    assert m.call_count == 3
    assert len(vectors) == 3


def test_embed_float_conversion_preserves_values() -> None:
    # Arrange: mock returns known float values to verify float() conversion
    chunks = [_chunk(0)]
    mock_resp: dict[str, Any] = {"data": [{"embedding": [1, 2, 3]}]}  # ints in, floats out

    # Act
    with patch(_PATCH, return_value=mock_resp):
        embedder = LLMEmbedder(provider="voyage", model="voyage-3")
        vectors = embedder.embed(chunks)

    # Assert — values are converted to float and preserved
    assert vectors[0] == [1.0, 2.0, 3.0]
    assert all(isinstance(v, float) for v in vectors[0])


# ── Protocol conformance ───────────────────────────────────────────────────────


def test_llm_embedder_satisfies_embedder_protocol() -> None:
    assert isinstance(LLMEmbedder(provider="voyage", model="voyage-3"), Embedder)
