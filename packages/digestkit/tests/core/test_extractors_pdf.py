"""AC-006: PDFExtractor

実装ファイル: packages/digestkit/src/digestkit/extractors/pdf.py
対応 SR: SR-F-004 (Extractor)
Fixtures: tests/fixtures/pdf/sample.pdf + corrupted.pdf
"""

from __future__ import annotations

from pathlib import Path

import pytest

from digestkit.extractors.pdf import ExtractionError, PDFExtractor
from digestkit.types import Item

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "pdf"


@pytest.mark.slow
def test_pdf_extractor_extracts_known_text_from_sample() -> None:
    """AC-006: 既知本文を持つ sample.pdf から主要文字列が抽出される."""
    # Arrange
    extractor = PDFExtractor()
    item = Item(id="sample", payload=_FIXTURE_DIR / "sample.pdf")

    # Act
    text = extractor.extract(item)

    # Assert
    assert "DigestKit Sample PDF Document" in text
    assert "Known text for AC-006 verification" in text


def test_pdf_extractor_raises_extraction_error_on_corrupted_pdf() -> None:
    """AC-006 異常系: 破損 PDF (ヘッダのみ) で ExtractionError."""
    # Arrange
    extractor = PDFExtractor()
    item = Item(id="corrupted", payload=_FIXTURE_DIR / "corrupted.pdf")

    # Act / Assert
    with pytest.raises(ExtractionError):
        extractor.extract(item)


def test_pdf_extractor_extraction_error_is_digestkit_error() -> None:
    """ExtractionError が DigestkitError を継承している."""
    # Arrange
    from digestkit.types import DigestkitError

    # Assert (静的な継承関係の確認)
    assert issubclass(ExtractionError, DigestkitError)


def test_pdf_extractor_raises_extraction_error_on_nonexistent_file() -> None:
    """存在しないファイルパスを渡した場合に ExtractionError が送出される."""
    # Arrange
    extractor = PDFExtractor()
    item = Item(id="missing", payload=Path("/nonexistent/path/file.pdf"))

    # Act / Assert
    with pytest.raises(ExtractionError):
        extractor.extract(item)
