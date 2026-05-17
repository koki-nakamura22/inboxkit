from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from digestkit_core.types import Item

__all__ = ["Extractor", "Source"]


@runtime_checkable
class Source(Protocol):
    def fetch(self) -> Iterable[Item]: ...


@runtime_checkable
class Extractor(Protocol):
    def extract(self, item: Item) -> str: ...
