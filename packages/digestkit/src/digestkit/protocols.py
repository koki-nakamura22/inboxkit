from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from digestkit.types import Digest, Item


@runtime_checkable
class Source(Protocol):
    def fetch(self) -> Iterable[Item]: ...


@runtime_checkable
class Extractor(Protocol):
    def extract(self, item: Item) -> str: ...


@runtime_checkable
class Summarizer(Protocol):
    def summarize(self, text: str, item: Item) -> Digest: ...


@runtime_checkable
class Sink(Protocol):
    def write(self, digest: Digest, item: Item) -> None: ...
