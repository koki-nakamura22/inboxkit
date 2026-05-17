from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


class DigestkitError(Exception):
    """digestkit エコシステム共通の例外 base."""


class ConfigurationError(DigestkitError):
    """Source / Extractor / その他コンポーネントの設定不備."""


@dataclass(frozen=True)
class Item:
    id: str
    payload: Any  # type depends on Source (e.g. Path for LocalDirectorySource)
    metadata: dict[str, Any] | None = None
    """Source 由来の補助情報 (例: Notion page object 全体).

    payload を Extractor が期待する型 (URL 文字列など) に揃えつつ、
    AckSource の callback などで元データを参照する用途で使う.
    """


@dataclass(frozen=True)
class Digest:
    summary: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str


FailureStage = Literal["extract", "summarize", "write"]


@dataclass(frozen=True)
class FailureInfo:
    item: Item
    stage: FailureStage
    error: BaseException
