"""Sink 実装の re-export.

`SlackSink` は `slack` extra (`httpx`) を、`NotionPageSink` は `notion` extra
(`notion-client`) を要求するため、eager import すると当該依存未インストール環境で
`digestkit.sinks` 自体が壊れる (Issue #2 と同型)。
PEP 562 `__getattr__` で遅延 import し、参照された時点で初めて依存を要求する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..types import DigestkitError


class SinkError(DigestkitError):
    """Sink 書き込み失敗."""


# 依存が標準ライブラリのみで完結する Sink は eager import で OK.
# 注: 各サブモジュールは `from . import SinkError` するため、SinkError 定義より下に置く。
from .composite import CompositeSink, CompositeSinkError  # noqa: E402
from .email import EmailSink  # noqa: E402
from .sqlite import SQLiteSink  # noqa: E402

if TYPE_CHECKING:
    from .notion_page import NotionPageSink
    from .slack import SlackSink

__all__ = [
    "CompositeSink",
    "CompositeSinkError",
    "EmailSink",
    "NotionPageSink",
    "SQLiteSink",
    "SinkError",
    "SlackSink",
]


def __getattr__(name: str) -> Any:
    if name == "SlackSink":
        from .slack import SlackSink

        return SlackSink
    if name == "NotionPageSink":
        from .notion_page import NotionPageSink

        return NotionPageSink
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
