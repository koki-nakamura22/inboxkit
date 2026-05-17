"""digestkit_core.extractors の smoke テスト."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from digestkit_core.extractors import ExtractionError, PDFExtractor
from digestkit_core.extractors.pdf import ExtractionError as ExtractionErrorDirect
from digestkit_core.extractors.pdf import PDFExtractor as PDFExtractorDirect
from digestkit_core.extractors.webpage import WebPageExtractor
from digestkit_core.types import DigestkitError, Item


def test_extraction_error_importable() -> None:
    assert ExtractionError is not None


def test_pdf_extractor_importable() -> None:
    assert PDFExtractor is not None


def test_webpage_extractor_importable() -> None:
    assert WebPageExtractor is not None


def test_extraction_error_is_canonical() -> None:
    assert ExtractionError is ExtractionErrorDirect


def test_pdf_extractor_is_canonical() -> None:
    assert PDFExtractor is PDFExtractorDirect


def test_extraction_error_is_digestkit_error() -> None:
    assert issubclass(ExtractionError, DigestkitError)


def test_pdf_extractor_invalid_path() -> None:
    extractor = PDFExtractor()
    item = Item(id="x", payload=Path("/nonexistent/file.pdf"))
    with pytest.raises(ExtractionError):
        extractor.extract(item)


def test_pdf_extractor_non_pdf_file() -> None:
    extractor = PDFExtractor()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"not a pdf")
        tmp_path = Path(f.name)
    try:
        item = Item(id="x", payload=tmp_path)
        with pytest.raises(ExtractionError):
            extractor.extract(item)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_webpage_extractor_default_timeout() -> None:
    extractor = WebPageExtractor()
    assert extractor._timeout == 30.0  # pyright: ignore[reportPrivateUsage]


def test_webpage_extractor_custom_timeout() -> None:
    extractor = WebPageExtractor(timeout=10.0)
    assert extractor._timeout == 10.0  # pyright: ignore[reportPrivateUsage]
