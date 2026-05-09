from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DigestkitError(Exception):
    """digestkit 固有例外の base."""


@dataclass(frozen=True)
class Item:
    id: str
    payload: Any  # type depends on Source (e.g. Path for LocalDirectorySource)


@dataclass(frozen=True)
class Digest:
    summary: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str
