"""Smoke test: README Quickstart の top-level import が動作すること.

Issue #1 (README が示す top-level import が __init__.py の re-export 漏れで動かない)
の再発防止。README を変更したらここも追従する。
"""

from __future__ import annotations


def test_readme_quickstart_imports() -> None:
    """README packages/digestkit/README.md Quickstart のコピペ import が成功する."""
    from digestkit import Digester
    from digestkit.extractors import PDFExtractor
    from digestkit.sinks import SQLiteSink
    from digestkit.sources import LocalDirectorySource
    from digestkit.summarizers import LLMSummarizer

    # 解決後の参照が None でない (再エクスポートが正しく解決されている)
    assert Digester is not None
    assert LocalDirectorySource is not None
    assert PDFExtractor is not None
    assert LLMSummarizer is not None
    assert SQLiteSink is not None


def test_top_level_public_api() -> None:
    """digestkit トップレベルの主要シンボルが re-export されている."""
    import digestkit

    assert digestkit.Digester is not None
    assert digestkit.RunResult is not None
    assert digestkit.FailureInfo is not None
    assert digestkit.ConfigurationError is not None
    assert digestkit.DigestkitError is not None
    assert issubclass(digestkit.ConfigurationError, digestkit.DigestkitError)


def test_sinks_public_api() -> None:
    """digestkit.sinks の主要 Sink クラスが re-export されている."""
    from digestkit.sinks import (
        CompositeSink,
        EmailSink,
        NotionPageSink,
        SinkError,
        SlackSink,
        SQLiteSink,
    )

    assert CompositeSink is not None
    assert EmailSink is not None
    assert NotionPageSink is not None
    assert SinkError is not None
    assert SlackSink is not None
    assert SQLiteSink is not None


def test_summarizers_public_api() -> None:
    """digestkit.summarizers.LLMSummarizer が re-export されている."""
    from digestkit.summarizers import LLMSummarizer

    assert LLMSummarizer is not None
