from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import final

from digestkit.dedup import SeenStore, SQLiteSeenStore, default_seen_store_path
from digestkit.protocols import Extractor, Sink, Source, Summarizer
from digestkit.types import DigestkitError, Item

logger = logging.getLogger(__name__)

_REQUIRED_ATTRS = ("source", "extractor", "summarizer", "sink")


@final
class _SeenStoreSentinel:
    """Sentinel distinguishing "not provided" from explicit None in Digester.__init__."""


_SEEN_STORE_UNSET = _SeenStoreSentinel()


class ConfigurationError(DigestkitError):
    """Digester サブクラスの設定不備 (必須属性欠落 等)."""


@dataclass(frozen=True)
class FailureInfo:
    item: Item
    stage: str  # "extract" | "summarize" | "write"
    error: BaseException


@dataclass
class RunResult:
    success: int = 0
    skipped: int = 0
    failures: list[FailureInfo] = field(default_factory=lambda: [])


class Digester:
    source: Source
    extractor: Extractor
    summarizer: Summarizer
    sink: Sink
    # Subclasses may override: seen_store: SeenStore | None = <value>
    # If not overridden, __init__ creates the default SQLiteSeenStore.
    # Set seen_store = None in a subclass or pass seen_store=None to disable dedup.

    def __init__(
        self, *, seen_store: SeenStore | None | _SeenStoreSentinel = _SEEN_STORE_UNSET
    ) -> None:
        missing = [a for a in _REQUIRED_ATTRS if not hasattr(self, a)]
        if missing:
            raise ConfigurationError(f"Missing required attributes: {missing}")

        if not isinstance(seen_store, _SeenStoreSentinel):
            self.seen_store: SeenStore | None = seen_store
        elif not hasattr(self, "seen_store"):
            self.seen_store = SQLiteSeenStore(default_seen_store_path(type(self).__name__))
        # else: subclass defined seen_store as class attribute; leave it as-is

    def run(self, limit: int | None = None, dry_run: bool = False) -> RunResult:
        result = RunResult()
        items = self.source.fetch()
        processed = 0

        for item in items:
            if limit is not None and processed >= limit:
                break

            if not dry_run and self.seen_store is not None and self.seen_store.has(item.id):
                result.skipped += 1
                processed += 1
                continue

            try:
                text = self.extractor.extract(item)
            except Exception as exc:
                logger.warning("extract failed for item %s: %s", item.id, exc)
                result.failures.append(FailureInfo(item=item, stage="extract", error=exc))
                processed += 1
                continue

            try:
                digest = self.summarizer.summarize(text, item)
            except Exception as exc:
                logger.warning("summarize failed for item %s: %s", item.id, exc)
                result.failures.append(FailureInfo(item=item, stage="summarize", error=exc))
                processed += 1
                continue

            if dry_run:
                result.skipped += 1
            else:
                try:
                    self.sink.write(digest, item)
                    result.success += 1
                    if self.seen_store is not None:
                        self.seen_store.add(item.id)
                except Exception as exc:
                    logger.warning("sink.write failed for item %s: %s", item.id, exc)
                    result.failures.append(FailureInfo(item=item, stage="write", error=exc))

            processed += 1

        logger.info(
            "run complete: success=%d skipped=%d failures=%d",
            result.success,
            result.skipped,
            len(result.failures),
        )
        return result
