"""AC-003 / AC-003b: FixedSizeChunker — char unit and token unit boundary conditions."""
from __future__ import annotations

import pytest
import tiktoken

from rag_ingest._upstream import Item
from rag_ingest.chunkers import FixedSizeChunker
from rag_ingest.protocols import Chunker


def _item(id: str = "test-item") -> Item:
    return Item(id=id, payload="")


def _expected_chunk_count(total: int, chunk_size: int, overlap: int) -> int:
    """Mirror of FixedSizeChunker._sliding_window termination logic."""
    if total == 0:
        return 0
    step = chunk_size - overlap
    count = 0
    start = 0
    while start < total:
        end = min(start + chunk_size, total)
        count += 1
        if end == total:
            break
        start += step
    return count


# ── AC-003: char unit boundary ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected_count",
    [
        ("", 0),
        ("abc", 1),
        ("a" * 10, 1),
        ("a" * 15, 2),
        ("a" * 100, 13),
    ],
)
def test_char_unit_boundary(text: str, expected_count: int) -> None:
    chunker = FixedSizeChunker(chunk_size=10, overlap=2, unit="char")
    chunks = chunker.chunk(text, _item())
    assert len(chunks) == expected_count


def test_char_unit_chunk_index_is_zero_based_sequential() -> None:
    chunker = FixedSizeChunker(chunk_size=10, overlap=2, unit="char")
    chunks = chunker.chunk("a" * 100, _item())
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_char_unit_empty_returns_no_chunks() -> None:
    chunker = FixedSizeChunker(chunk_size=10, overlap=2, unit="char")
    assert chunker.chunk("", _item()) == []


def test_char_unit_exact_size_is_single_chunk() -> None:
    chunker = FixedSizeChunker(chunk_size=5, overlap=1, unit="char")
    chunks = chunker.chunk("abcde", _item())
    assert len(chunks) == 1
    assert chunks[0].text == "abcde"


def test_char_unit_overlap_content_shared_between_consecutive_chunks() -> None:
    # chunk_size=5, overlap=2 → step=3
    # text="abcdefgh" (8 chars)
    # chunk0=[0:5]="abcde", chunk1=[3:8]="defgh"
    chunker = FixedSizeChunker(chunk_size=5, overlap=2, unit="char")
    chunks = chunker.chunk("abcdefgh", _item())
    assert len(chunks) == 2
    assert chunks[0].text == "abcde"
    assert chunks[1].text == "defgh"
    # last 2 chars of chunk0 == first 2 chars of chunk1
    assert chunks[0].text[-2:] == chunks[1].text[:2]


def test_char_unit_last_chunk_may_be_shorter_than_chunk_size() -> None:
    chunker = FixedSizeChunker(chunk_size=10, overlap=2, unit="char")
    chunks = chunker.chunk("a" * 15, _item())
    assert len(chunks[1].text) < 10


def test_char_unit_metadata_contains_source_id() -> None:
    chunker = FixedSizeChunker(chunk_size=5, overlap=0, unit="char")
    chunks = chunker.chunk("hello", _item(id="src-42"))
    assert chunks[0].metadata["source_id"] == "src-42"


# ── AC-003b: token unit ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello world",
        "The quick brown fox jumps over the lazy dog. " * 3,
        "日本語のテキストです。チャンクのテストに使います。" * 5,
        "word " * 200,  # ~400 tokens, forces multiple chunks
    ],
)
def test_token_unit_chunk_count_matches_tiktoken(text: str) -> None:
    enc = tiktoken.get_encoding("cl100k_base")
    chunker = FixedSizeChunker(chunk_size=100, overlap=10, unit="token")
    chunks = chunker.chunk(text, _item())
    token_count = len(enc.encode(text))
    expected = _expected_chunk_count(token_count, 100, 10)
    assert len(chunks) == expected


def test_token_unit_chunk_index_is_zero_based_sequential() -> None:
    chunker = FixedSizeChunker(chunk_size=50, overlap=5, unit="token")
    chunks = chunker.chunk("word " * 200, _item())
    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_token_unit_each_chunk_decodes_to_nonempty_string() -> None:
    chunker = FixedSizeChunker(chunk_size=20, overlap=5, unit="token")
    chunks = chunker.chunk("The quick brown fox. " * 10, _item())
    for chunk in chunks:
        assert isinstance(chunk.text, str)
        assert len(chunk.text) > 0


def test_token_unit_empty_text_returns_no_chunks() -> None:
    chunker = FixedSizeChunker(chunk_size=100, overlap=10, unit="token")
    assert chunker.chunk("", _item()) == []


def test_token_unit_short_text_within_single_chunk() -> None:
    chunker = FixedSizeChunker(chunk_size=100, overlap=10, unit="token")
    text = "hello world"
    chunks = chunker.chunk(text, _item())
    assert len(chunks) == 1


def test_token_unit_first_and_second_chunk_overlap_in_token_space() -> None:
    enc = tiktoken.get_encoding("cl100k_base")
    chunker = FixedSizeChunker(chunk_size=10, overlap=3, unit="token")
    text = "word " * 30
    chunks = chunker.chunk(text, _item())
    assert len(chunks) >= 2
    tokens_0 = enc.encode(chunks[0].text)
    tokens_1 = enc.encode(chunks[1].text)
    # last 3 tokens of chunk0 == first 3 tokens of chunk1
    assert tokens_0[-3:] == tokens_1[:3]


def test_token_unit_metadata_contains_source_id() -> None:
    chunker = FixedSizeChunker(chunk_size=100, overlap=10, unit="token")
    chunks = chunker.chunk("hello world", _item(id="doc-99"))
    assert chunks[0].metadata["source_id"] == "doc-99"


# ── config property ────────────────────────────────────────────────────────────


def test_config_default_values() -> None:
    chunker = FixedSizeChunker()
    assert chunker.config == {"chunk_size": 512, "overlap": 64, "unit": "token"}


def test_config_reflects_constructor_args() -> None:
    chunker = FixedSizeChunker(chunk_size=100, overlap=10, unit="char")
    assert chunker.config == {"chunk_size": 100, "overlap": 10, "unit": "char"}


# ── Protocol conformance ───────────────────────────────────────────────────────


def test_fixed_size_chunker_is_chunker_protocol() -> None:
    assert isinstance(FixedSizeChunker(), Chunker)


def test_fixed_size_chunker_char_unit_is_chunker_protocol() -> None:
    assert isinstance(FixedSizeChunker(unit="char"), Chunker)
