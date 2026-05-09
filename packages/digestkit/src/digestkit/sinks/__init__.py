from __future__ import annotations

from ..types import DigestkitError


class SinkError(DigestkitError):
    """Sink 書き込み失敗."""


# Re-export concrete sinks. Imports placed below SinkError because submodules
# do `from . import SinkError` (would otherwise circular-import on package load).
from .composite import CompositeSink, CompositeSinkError  # noqa: E402
from .email import EmailSink  # noqa: E402
from .slack import SlackSink  # noqa: E402
from .sqlite import SQLiteSink  # noqa: E402

__all__ = [
    "CompositeSink",
    "CompositeSinkError",
    "EmailSink",
    "SQLiteSink",
    "SinkError",
    "SlackSink",
]
