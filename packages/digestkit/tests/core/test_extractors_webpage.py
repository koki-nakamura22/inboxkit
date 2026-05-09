"""AC-007: WebPageExtractor (httpx mock)

実装ファイル: packages/digestkit/src/digestkit/extractors/webpage.py
対応 SR: SR-F-004 (Extractor)
Fixtures: tests/fixtures/web/article.html + 404.html
"""

from __future__ import annotations

import pytest


def test_webpage_extractor_returns_article_body_only() -> None:
    """AC-007: trafilatura が抽出した本文のみ返り、ヘッダ/フッタは含まない."""
    pytest.fail("not yet implemented")


def test_webpage_extractor_raises_extraction_error_on_404() -> None:
    """AC-007 異常系: 404 レスポンスで ExtractionError."""
    pytest.fail("not yet implemented")


def test_webpage_extractor_raises_extraction_error_on_timeout() -> None:
    """AC-007 異常系: タイムアウトで ExtractionError."""
    pytest.fail("not yet implemented")
