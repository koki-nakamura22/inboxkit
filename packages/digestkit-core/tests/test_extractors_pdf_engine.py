"""PDFExtractor のエンジン選択 (Issue #55) に関するテスト.

実装ファイル: packages/digestkit-core/src/digestkit_core/extractors/pdf.py

Issue #55 の本題 (`/Encoding /Identity-H` + Adobe-Japan1 ordering + ToUnicode 欠落の
CID フォント埋め込み PDF での文字化け) は**合成 PDF で再現できない**ため、ここでは
再現テストを持たない。ToUnicode を落とすと ordering が Identity に落ちて pypdfium2 でも
読めなくなり、実物と同じ条件にならないためである。
本ファイルが担保するのは「エンジン選択・委譲・エラー正規化・両エンジンの振る舞い等価性」まで。
実物 PDF での確認は手動で行う。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from digestkit_core.extractors.pdf import (
    DEFAULT_ENGINE,
    ExtractionError,
    PDFEngine,
    PDFExtractor,
)
from digestkit_core.types import Item

ENGINES: tuple[PDFEngine, ...] = ("pypdfium2", "pypdf")

_KNOWN_TEXT = "Digestkit engine parity fixture"


def _build_pdf(page_texts: list[str | None]) -> bytes:
    """base14 フォントのみを使う最小 PDF を組み立てる.

    `page_texts` の各要素が 1 ページに対応し、None はコンテンツストリームを持たない
    (= 本文なし) ページ。外部ライブラリを使わずバイト列を直接組むことで、fixture
    ファイル無しで両エンジンに同一入力を与えられるようにしている.
    """
    parts: list[bytes] = [b"%PDF-1.4\n"]
    offsets: list[int] = []

    def add(body: bytes) -> None:
        offsets.append(sum(len(p) for p in parts))
        num = len(offsets)
        parts.append(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")

    # obj 1 = Catalog, obj 2 = Pages, obj 3 = 共有 Font,
    # obj 4.. = Page / Contents (本文ありページは 2 obj 消費)
    first_page_obj = 4
    page_obj_nums: list[int] = []
    next_obj = first_page_obj
    for text in page_texts:
        page_obj_nums.append(next_obj)
        next_obj += 1 if text is None else 2

    kids = b" ".join(f"{n} 0 R".encode() for n in page_obj_nums)
    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    add(b"<< /Type /Pages /Kids [" + kids + f"] /Count {len(page_texts)} >>".encode())
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_num, text in zip(page_obj_nums, page_texts, strict=True):
        if text is None:
            add(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")
            continue
        contents_num = page_num + 1
        add(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> " + f"/Contents {contents_num} 0 R >>".encode()
        )
        stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode("ascii") + b") Tj ET"
        add(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")

    xref_pos = sum(len(p) for p in parts)
    count = len(offsets) + 1
    xref = f"xref\n0 {count}\n0000000000 65535 f \n".encode()
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return b"".join(parts) + xref + trailer


@pytest.fixture
def text_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "text.pdf"
    path.write_bytes(_build_pdf([_KNOWN_TEXT]))
    return path


# --- エンジン選択 -----------------------------------------------------------


def test_default_engine_is_pypdfium2() -> None:
    """Issue #55: 既定エンジンは pypdfium2 (pypdf は CID 日本語 PDF で文字化けするため)."""
    # Arrange / Act
    extractor = PDFExtractor()

    # Assert
    assert extractor.engine == "pypdfium2"
    assert DEFAULT_ENGINE == "pypdfium2"


@pytest.mark.parametrize("engine", ENGINES)
def test_explicit_engine_is_retained(engine: PDFEngine) -> None:
    """明示指定したエンジンがそのまま保持される (有効同値クラス)."""
    # Arrange / Act
    extractor = PDFExtractor(engine=engine)

    # Assert
    assert extractor.engine == engine


@pytest.mark.parametrize("engine", ["", "PYPDF", "pdfminer", "pypdfium"])
def test_unknown_engine_raises_value_error(engine: str) -> None:
    """未知のエンジン名は構築時点で ValueError (無効同値クラス)."""
    # Act / Assert
    with pytest.raises(ValueError, match="Unknown PDF engine"):
        PDFExtractor(engine=engine)  # pyright: ignore[reportArgumentType]


def test_unknown_engine_message_lists_valid_engines() -> None:
    """エラーメッセージが有効なエンジン名を案内する."""
    # Act / Assert
    with pytest.raises(ValueError) as excinfo:
        PDFExtractor(engine="pdfminer")  # pyright: ignore[reportArgumentType]

    message = str(excinfo.value)
    assert "'pypdfium2'" in message
    assert "'pypdf'" in message


# --- エンジンごとの委譲 -----------------------------------------------------


@pytest.mark.parametrize("engine", ENGINES)
def test_extract_returns_known_text(engine: PDFEngine, text_pdf: Path) -> None:
    """両エンジンとも本文を持つ PDF から既知文字列を抽出する."""
    # Arrange
    extractor = PDFExtractor(engine=engine)
    item = Item(id="text", payload=text_pdf)

    # Act
    text = extractor.extract(item)

    # Assert
    assert _KNOWN_TEXT in text


@pytest.mark.parametrize("engine", ENGINES)
def test_extract_covers_every_page(engine: PDFEngine, tmp_path: Path) -> None:
    """複数ページ PDF で全ページの本文が結合される (ページ抜け / off-by-one の検出)."""
    # Arrange
    page_texts = ["Page one body", "Page two body", "Page three body"]
    path = tmp_path / "multipage.pdf"
    path.write_bytes(_build_pdf(list(page_texts)))
    extractor = PDFExtractor(engine=engine)
    item = Item(id="multipage", payload=path)

    # Act
    text = extractor.extract(item)

    # Assert
    for page_text in page_texts:
        assert page_text in text
    assert text.index(page_texts[0]) < text.index(page_texts[2])


def test_pypdfium2_normalizes_crlf_to_lf(text_pdf: Path) -> None:
    """PDFium は CRLF を返すため、pypdf エンジンと揃えて LF に正規化する."""
    # Arrange
    extractor = PDFExtractor(engine="pypdfium2")
    item = Item(id="text", payload=text_pdf)

    # Act
    text = extractor.extract(item)

    # Assert — 本文が取れた上で CR が残っていないこと (空文字での vacuous pass を防ぐ)
    assert _KNOWN_TEXT in text
    assert "\r" not in text


@pytest.mark.parametrize("engine", ENGINES)
def test_extract_returns_empty_string_for_pdf_with_no_text(
    engine: PDFEngine, tmp_path: Path
) -> None:
    """D-102: 本文なしの有効 PDF は両エンジンとも空文字列 (ExtractionError ではない)."""
    # Arrange
    path = tmp_path / "empty.pdf"
    path.write_bytes(_build_pdf([None]))
    extractor = PDFExtractor(engine=engine)
    item = Item(id="empty", payload=path)

    # Act
    result = extractor.extract(item)

    # Assert
    assert result.strip() == ""


# --- 異常系: エラー正規化 --------------------------------------------------


@pytest.mark.parametrize("engine", ENGINES)
def test_nonexistent_path_raises_extraction_error(engine: PDFEngine) -> None:
    """存在しないパスは両エンジンとも ExtractionError に正規化される."""
    # Arrange
    extractor = PDFExtractor(engine=engine)
    item = Item(id="missing", payload=Path("/nonexistent/path/file.pdf"))

    # Act / Assert
    with pytest.raises(ExtractionError):
        extractor.extract(item)


@pytest.mark.parametrize("engine", ENGINES)
def test_non_pdf_content_raises_extraction_error(engine: PDFEngine, tmp_path: Path) -> None:
    """PDF ではないファイルは両エンジンとも ExtractionError に正規化される."""
    # Arrange
    path = tmp_path / "not-a.pdf"
    path.write_bytes(b"not a pdf")
    extractor = PDFExtractor(engine=engine)
    item = Item(id="broken", payload=path)

    # Act / Assert
    with pytest.raises(ExtractionError):
        extractor.extract(item)


@pytest.mark.parametrize("engine", ENGINES)
def test_truncated_pdf_raises_extraction_error(engine: PDFEngine, tmp_path: Path) -> None:
    """ヘッダのみの破損 PDF は両エンジンとも ExtractionError に正規化される."""
    # Arrange
    path = tmp_path / "corrupted.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    extractor = PDFExtractor(engine=engine)
    item = Item(id="corrupted", payload=path)

    # Act / Assert
    with pytest.raises(ExtractionError):
        extractor.extract(item)


# --- 異常系: 依存欠落 ------------------------------------------------------


@pytest.mark.parametrize(
    ("engine", "extra"),
    [("pypdfium2", "pdf"), ("pypdf", "pdf-pypdf")],
)
def test_missing_engine_dependency_reports_extra_name(
    engine: PDFEngine,
    extra: str,
    text_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """エンジン未インストール時は ExtractionError で必要な extra 名を案内する."""
    # Arrange — sys.modules に None を置くと import が ImportError になる
    monkeypatch.setitem(sys.modules, engine, None)
    extractor = PDFExtractor(engine=engine)
    item = Item(id="text", payload=text_pdf)

    # Act / Assert
    with pytest.raises(ExtractionError) as excinfo:
        extractor.extract(item)

    # `extra in message` だけだと、ファイルパス由来のメッセージ (".pdf") でも
    # 部分一致してしまうため、依存欠落固有の文言も合わせて検証する。
    message = str(excinfo.value)
    assert "is not installed" in message
    assert engine in message
    assert f"[{extra}]" in message
