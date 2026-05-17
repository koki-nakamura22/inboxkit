from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import tiktoken

from rag_ingest._upstream import Item
from rag_ingest.types import Chunk


class FixedSizeChunker:
    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 64,
        unit: Literal["token", "char"] = "token",
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.unit = unit
        self._enc: tiktoken.Encoding | None = None
        if unit == "token":
            self._enc = tiktoken.get_encoding("cl100k_base")

    def chunk(self, text: str, item: Item) -> list[Chunk]:
        if self.unit == "token":
            enc = self._enc
            assert enc is not None
            token_ids = enc.encode(text)
            return self._sliding_window(
                total=len(token_ids),
                get_slice=lambda s, e: enc.decode(token_ids[s:e]),
                item=item,
            )
        return self._sliding_window(
            total=len(text),
            get_slice=lambda s, e: text[s:e],
            item=item,
        )

    def _sliding_window(
        self,
        total: int,
        get_slice: Callable[[int, int], str],
        item: Item,
    ) -> list[Chunk]:
        if total == 0:
            return []
        step = self.chunk_size - self.overlap
        result: list[Chunk] = []
        start = 0
        while start < total:
            end = min(start + self.chunk_size, total)
            result.append(
                Chunk(
                    text=get_slice(start, end),
                    chunk_index=len(result),
                    metadata={"source_id": item.id},
                )
            )
            if end == total:
                break
            start += step
        return result

    @property
    def config(self) -> dict[str, Any]:
        return {
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
            "unit": self.unit,
        }
