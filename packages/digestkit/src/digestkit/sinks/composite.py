from __future__ import annotations

from ..digester import ConfigurationError
from ..protocols import Sink
from ..types import Digest, Item
from . import SinkError


class CompositeSinkError(SinkError):
    def __init__(self, errors: list[BaseException]) -> None:
        super().__init__(f"{len(errors)} sink(s) failed: " + "; ".join(str(e) for e in errors))
        self.errors = errors


class CompositeSink:
    def __init__(self, sinks: list[Sink]) -> None:
        if not sinks:
            raise ConfigurationError("CompositeSink requires at least 1 sink")
        self._sinks = list(sinks)

    def write(self, digest: Digest, item: Item) -> None:
        errors: list[BaseException] = []
        for sink in self._sinks:
            try:
                sink.write(digest, item)
            except Exception as e:
                errors.append(e)
        if errors:
            raise CompositeSinkError(errors)

    def __add__(self, other: Sink) -> CompositeSink:
        return CompositeSink([*self._sinks, other])
