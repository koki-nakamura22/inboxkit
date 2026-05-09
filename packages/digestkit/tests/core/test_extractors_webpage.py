"""AC-007: WebPageExtractor (httpx mock)

実装ファイル: packages/digestkit/src/digestkit/extractors/webpage.py
対応 SR: SR-F-004 (Extractor)
Fixtures: tests/fixtures/web/article.html + 404.html
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from digestkit.extractors.pdf import ExtractionError
from digestkit.extractors.webpage import WebPageExtractor
from digestkit.types import Item

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "web"


def _make_ok_response(html: str, content_type: str = "text/html; charset=utf-8") -> MagicMock:
    response: MagicMock = MagicMock(spec=httpx.Response)
    response.text = html
    response.headers = {"content-type": content_type}
    response.raise_for_status.return_value = None
    return response


def _make_error_response(status_code: int) -> MagicMock:
    mock_request: MagicMock = MagicMock(spec=httpx.Request)
    response: MagicMock = MagicMock(spec=httpx.Response)
    response.headers = {"content-type": "text/html"}
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        str(status_code), request=mock_request, response=response
    )
    return response


def test_webpage_extractor_returns_article_body_only() -> None:
    """AC-007: trafilatura が抽出した本文のみ返り、ヘッダ/フッタは含まない."""
    # Arrange
    html = (_FIXTURE_DIR / "article.html").read_text()
    item = Item(id="article", payload="https://example.com/article")

    # Act
    with patch("httpx.get", return_value=_make_ok_response(html)):
        extractor = WebPageExtractor()
        text = extractor.extract(item)

    # Assert
    assert "first paragraph" in text
    assert "HEADER NAVIGATION" not in text
    assert "FOOTER" not in text


def test_webpage_extractor_raises_extraction_error_on_404() -> None:
    """AC-007 異常系: 404 レスポンスで ExtractionError."""
    # Arrange
    item = Item(id="missing", payload="https://example.com/missing")

    # Act / Assert
    with patch("httpx.get", return_value=_make_error_response(404)):
        extractor = WebPageExtractor()
        with pytest.raises(ExtractionError):
            extractor.extract(item)


def test_webpage_extractor_raises_extraction_error_on_timeout() -> None:
    """AC-007 異常系: タイムアウトで ExtractionError."""
    # Arrange
    item = Item(id="slow", payload="https://example.com/slow")

    # Act / Assert
    with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
        extractor = WebPageExtractor()
        with pytest.raises(ExtractionError):
            extractor.extract(item)
