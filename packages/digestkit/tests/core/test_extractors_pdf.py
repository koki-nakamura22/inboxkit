"""AC-006: PDFExtractor

実装ファイル: packages/digestkit/src/digestkit/extractors/pdf.py
対応 SR: SR-F-004 (Extractor)
Fixtures: tests/fixtures/pdf/sample.pdf + corrupted.pdf
"""

from __future__ import annotations

import pytest


@pytest.mark.slow
def test_pdf_extractor_extracts_known_text_from_sample() -> None:
    """AC-006: 既知本文を持つ sample.pdf から主要文字列が抽出される."""
    pytest.fail("not yet implemented")


def test_pdf_extractor_raises_extraction_error_on_corrupted_pdf() -> None:
    """AC-006 異常系: 破損 PDF (ヘッダのみ) で ExtractionError."""
    pytest.fail("not yet implemented")
