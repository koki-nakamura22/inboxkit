from __future__ import annotations

import logging
from dataclasses import dataclass, field

from digestkit.protocols import Extractor, Sink, Source, Summarizer
from digestkit.types import Item

logger = logging.getLogger(__name__)

_REQUIRED_ATTRS = ("source", "extractor", "summarizer", "sink")


class DigestkitError(Exception):
    """digestkit 固有例外の base."""


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

    def __init__(self) -> None:
        missing = [a for a in _REQUIRED_ATTRS if not hasattr(self, a)]
        if missing:
            raise ConfigurationError(f"Missing required attributes: {missing}")

    def run(self, limit: int | None = None, dry_run: bool = False) -> RunResult:
        result = RunResult()
        items = self.source.fetch()
        processed = 0

        for item in items:
            if limit is not None and processed >= limit:
                break

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
