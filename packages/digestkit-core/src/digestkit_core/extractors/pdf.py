from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args

from digestkit_core.types import DigestkitError, Item

PDFEngine = Literal["pypdfium2", "pypdf"]

DEFAULT_ENGINE: PDFEngine = "pypdfium2"

_ENGINE_EXTRAS: dict[PDFEngine, str] = {
    "pypdfium2": "pdf",
    "pypdf": "pdf-pypdf",
}


class ExtractionError(DigestkitError):
    """テキスト抽出失敗."""


def _missing_engine_error(engine: PDFEngine, exc: ImportError) -> ExtractionError:
    extra = _ENGINE_EXTRAS[engine]
    return ExtractionError(
        f"PDF engine {engine!r} is not installed. Install it via the {extra!r} extra "
        f"(e.g. pip install 'digestkit-core[{extra}]')."
    )


class PDFExtractor:
    """PDF からテキストを抽出する.

    既定の ``pypdfium2`` は PDFium のグリフ解析を使うため、``/Encoding /Identity-H`` +
    Adobe-Japan1 ordering の CID フォントを埋め込んだ日本語 PDF でも文字化けしない。
    ``pypdf`` は ToUnicode CMap を持たないフォントを補完できず、この種の PDF で
    **例外を出さずに**文字化けテキストを返す (Issue #55) ため既定から外した。
    """

    def __init__(self, engine: PDFEngine = DEFAULT_ENGINE) -> None:
        if engine not in _ENGINE_EXTRAS:
            valid = ", ".join(repr(e) for e in get_args(PDFEngine))
            raise ValueError(f"Unknown PDF engine: {engine!r} (expected one of {valid})")
        self._engine: PDFEngine = engine

    @property
    def engine(self) -> PDFEngine:
        return self._engine

    def extract(self, item: Item) -> str:
        path: Path = item.payload
        if self._engine == "pypdf":
            return self._extract_with_pypdf(path)
        return self._extract_with_pypdfium2(path)

    def _extract_with_pypdfium2(self, path: Path) -> str:
        try:
            import pypdfium2
        except ImportError as exc:
            raise _missing_engine_error("pypdfium2", exc) from exc

        try:
            document = pypdfium2.PdfDocument(path)
        except Exception as exc:
            raise ExtractionError(str(exc)) from exc

        try:
            pages: list[str] = []
            for index in range(len(document)):
                page = document[index]
                textpage = page.get_textpage()
                # PDFium は CRLF を返す。pypdf エンジンおよび後段 (要約 / chunk) と
                # 揃えるため LF に正規化する。
                # pypdfium2 の型情報は引数が Unknown のため strict で落ちる (第三者スタブ都合)
                raw = textpage.get_text_bounded()  # pyright: ignore[reportUnknownMemberType]
                text = str(raw or "")
                pages.append(text.replace("\r\n", "\n").replace("\r", "\n"))
            return "\n".join(pages)
        except Exception as exc:
            raise ExtractionError(str(exc)) from exc
        finally:
            document.close()

    def _extract_with_pypdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise _missing_engine_error("pypdf", exc) from exc

        try:
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ExtractionError(str(exc)) from exc
