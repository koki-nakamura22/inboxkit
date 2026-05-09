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


def _build_empty_pdf() -> bytes:
    """有効な PDF 構造だがテキストコンテンツを持たない最小 PDF を返す."""
    parts: list[bytes] = []
    offsets: list[int] = []

    parts.append(b"%PDF-1.4\n")

    def add(num: int, body: bytes) -> None:
        offsets.append(sum(len(p) for p in parts))
        parts.append(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")

    add(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    add(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add(3, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")

    xref_pos = sum(len(p) for p in parts)
    xref = b"xref\n0 4\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = (
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    return b"".join(parts) + xref + trailer


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


def test_pdf_extractor_returns_empty_string_for_pdf_with_no_text(tmp_path: Path) -> None:
    """D-102: テキストなしの有効 PDF は ExtractionError ではなく空文字列を返す."""
    # Arrange — 有効な PDF 構造だがコンテンツストリームなし
    pdf_bytes = _build_empty_pdf()
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(pdf_bytes)
    extractor = PDFExtractor()
    item = Item(id="empty", payload=pdf_path)

    # Act
    result = extractor.extract(item)

    # Assert
    assert isinstance(result, str)
    assert result.strip() == ""


def test_pdf_extractor_extraction_error_is_digestkit_error() -> None:
    """ExtractionError が DigestkitError を継承している."""
    from digestkit.types import DigestkitError

    assert issubclass(ExtractionError, DigestkitError)


def test_pdf_extractor_raises_extraction_error_on_nonexistent_file() -> None:
    """存在しないファイルパスを渡した場合に ExtractionError が送出される."""
    # Arrange
    extractor = PDFExtractor()
    item = Item(id="missing", payload=Path("/nonexistent/path/file.pdf"))

    # Act / Assert
    with pytest.raises(ExtractionError):
        extractor.extract(item)
