"""Phase 2c 互換テスト: digestkit-core 抽出後も Phase 1 公開 API が不変であること.

既存の test_public_api.py は README Quickstart import の smoke を検証する。
本ファイルは phase2c-compat-test-policy.md の (a)〜(e) を実装し、
canonical 同一性・シグネチャ不変・CLI 不変・dataclass フィールド不変を保証する。
"""

from __future__ import annotations

import dataclasses
import importlib.metadata as md
import inspect

# --- (a) Phase 1 公開 import path の網羅 ---


def test_phase1_protocols_import() -> None:
    from digestkit.protocols import AckSource, Extractor, Sink, Source, Summarizer

    assert all(p is not None for p in (Source, Extractor, AckSource, Summarizer, Sink))


def test_phase1_types_import() -> None:
    from digestkit.types import Digest, DigestkitError, Item

    assert all(t is not None for t in (Item, Digest, DigestkitError))


def test_phase1_sources_import() -> None:
    import digestkit.sources
    from digestkit.sources.local_directory import LocalDirectorySource
    from digestkit.sources.notion_database import NotionDatabaseSource

    assert digestkit.sources.LocalDirectorySource is LocalDirectorySource
    assert digestkit.sources.NotionDatabaseSource is NotionDatabaseSource


def test_phase1_extractors_import() -> None:
    import digestkit.extractors
    import digestkit.extractors.webpage
    from digestkit.extractors.pdf import PDFExtractor
    from digestkit.extractors.webpage import WebPageExtractor

    assert digestkit.extractors.PDFExtractor is PDFExtractor
    assert digestkit.extractors.webpage.WebPageExtractor is WebPageExtractor


# --- (b) canonical 同一性 ---


def test_protocols_are_canonical_in_core() -> None:
    from digestkit.protocols import Extractor, Source
    from digestkit_core.protocols import Extractor as CExtractor
    from digestkit_core.protocols import Source as CSource

    assert Source is CSource
    assert Extractor is CExtractor


def test_item_is_canonical_in_core() -> None:
    from digestkit.types import Item
    from digestkit_core.types import Item as CItem

    assert Item is CItem


def test_digest_is_canonical_in_core() -> None:
    from digestkit.types import Digest
    from digestkit_core.types import Digest as CDigest

    assert Digest is CDigest


def test_digestkit_error_is_canonical_in_core() -> None:
    from digestkit.types import DigestkitError
    from digestkit_core.types import DigestkitError as CDigestkitError

    assert DigestkitError is CDigestkitError


def test_concrete_sources_are_canonical_in_core() -> None:
    import digestkit_core.sources
    from digestkit.sources.local_directory import LocalDirectorySource
    from digestkit.sources.notion_database import NotionDatabaseSource

    assert LocalDirectorySource is digestkit_core.sources.LocalDirectorySource
    assert NotionDatabaseSource is digestkit_core.sources.NotionDatabaseSource


def test_extractors_are_canonical_in_core() -> None:
    from digestkit.extractors.pdf import ExtractionError, PDFExtractor
    from digestkit.extractors.webpage import WebPageExtractor
    from digestkit_core.extractors.pdf import ExtractionError as CExtractionError
    from digestkit_core.extractors.pdf import PDFExtractor as CPDFExtractor
    from digestkit_core.extractors.webpage import WebPageExtractor as CWebPageExtractor

    assert PDFExtractor is CPDFExtractor
    assert ExtractionError is CExtractionError
    assert WebPageExtractor is CWebPageExtractor


def test_failure_info_is_canonical_in_core() -> None:
    from digestkit.digester import FailureInfo
    from digestkit_core.types import FailureInfo as CFailureInfo

    assert FailureInfo is CFailureInfo


def test_configuration_error_is_canonical_in_core() -> None:
    from digestkit.digester import ConfigurationError
    from digestkit_core.types import ConfigurationError as CConfigurationError

    assert ConfigurationError is CConfigurationError


# --- (c) シグネチャ不変 ---


def test_digester_run_signature() -> None:
    from digestkit import Digester

    sig = inspect.signature(Digester.run)
    params = list(sig.parameters)
    assert params == ["self", "limit", "dry_run", "length"]
    assert sig.parameters["limit"].default is None
    assert sig.parameters["dry_run"].default is False
    assert sig.parameters["length"].kind == inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["length"].default is None


def test_local_directory_source_init_signature() -> None:
    from digestkit.sources.local_directory import LocalDirectorySource

    sig = inspect.signature(LocalDirectorySource.__init__)
    params = list(sig.parameters)
    assert params == ["self", "path", "glob"]
    assert sig.parameters["glob"].default == "*"


def test_pdf_extractor_extract_signature() -> None:
    from digestkit.extractors.pdf import PDFExtractor

    sig = inspect.signature(PDFExtractor.extract)
    params = list(sig.parameters)
    assert params == ["self", "item"]


def test_webpage_extractor_init_signature() -> None:
    from digestkit.extractors.webpage import WebPageExtractor

    sig = inspect.signature(WebPageExtractor.__init__)
    params = list(sig.parameters)
    assert params == ["self", "timeout"]
    assert sig.parameters["timeout"].default == 30.0


# --- (d) CLI コマンドの不変 ---


def test_cli_entrypoint_exists() -> None:
    from digestkit.cli import main

    assert callable(main)


def test_cli_command_registered() -> None:
    eps = md.entry_points(group="console_scripts")
    assert any(ep.name == "digestkit" for ep in eps)


# --- (e) Item / Digest dataclass フィールドの不変 ---


def test_item_fields_unchanged() -> None:
    from digestkit.types import Item

    fields = {f.name for f in dataclasses.fields(Item)}
    assert fields == {"id", "payload", "metadata"}


def test_digest_fields_unchanged() -> None:
    from digestkit.types import Digest

    fields = {f.name for f in dataclasses.fields(Digest)}
    assert fields == {"summary", "tokens_in", "tokens_out", "latency_ms", "model"}
