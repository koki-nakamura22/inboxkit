from __future__ import annotations

from pathlib import Path

from digestkit.types import DigestkitError, Item


class ExtractionError(DigestkitError):
    """テキスト抽出失敗."""


class PDFExtractor:
    def extract(self, item: Item) -> str:
        from pypdf import PdfReader
        from pypdf.errors import PdfStreamError

        path: Path = item.payload
        try:
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except PdfStreamError as exc:
            raise ExtractionError(str(exc)) from exc
        except Exception as exc:
            raise ExtractionError(str(exc)) from exc
