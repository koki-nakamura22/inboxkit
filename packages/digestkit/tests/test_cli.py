"""AC-011 / AC-011a〜f: CLI ランナー (`digestkit run`)

実装ファイル: packages/digestkit/src/digestkit/cli.py
対応 SR: SR-F-007
"""

from __future__ import annotations

from pathlib import Path

import pytest

from digestkit.cli import main


# Minimal valid Digester module: 2 items, no failures, seen_store=None (no SQLite)
_VALID_DIGESTER_MODULE = """\
from digestkit.digester import Digester
from digestkit.types import Item, Digest


class _Source:
    def fetch(self):
        return [Item(id="1", payload=None), Item(id="2", payload=None)]


class _Extractor:
    def extract(self, item):
        return f"text:{item.id}"


class _Summarizer:
    def summarize(self, text, item):
        return Digest(summary=text, tokens_in=1, tokens_out=1, latency_ms=0, model="stub")


class _Sink:
    def write(self, digest, item):
        pass


class MyDigester(Digester):
    source = _Source()
    extractor = _Extractor()
    summarizer = _Summarizer()
    sink = _Sink()
    seen_store = None
"""


def test_cli_run_executes_digester_and_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-011 正常系: 正しい Digester サブクラスを含む module を渡すと終了コード 0 + サマリ出力."""
    # Arrange
    module_file = tmp_path / "my_digester.py"
    module_file.write_text(_VALID_DIGESTER_MODULE)

    # Act
    exit_code = main(["run", str(module_file)])
    captured = capsys.readouterr()

    # Assert
    assert exit_code == 0
    assert "success=2" in captured.out
    assert "failures=0" in captured.out
    assert "skipped=0" in captured.out


def test_cli_run_returns_three_when_module_file_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC-011a: ファイル不在 → 終了コード 3 + stderr メッセージ."""
    # Act
    exit_code = main(["run", "/nonexistent/path/no_such_digester.py"])
    captured = capsys.readouterr()

    # Assert
    assert exit_code == 3
    assert "not found" in captured.err


def test_cli_run_returns_three_when_no_digester_subclass_found(tmp_path: Path) -> None:
    """AC-011b: Digester サブクラスゼロ個 → 終了コード 3."""
    # Arrange
    module_file = tmp_path / "no_digester.py"
    module_file.write_text("class Foo:\n    pass\n")

    # Act
    exit_code = main(["run", str(module_file)])

    # Assert
    assert exit_code == 3


def test_cli_run_returns_three_when_multiple_digester_subclasses_found(tmp_path: Path) -> None:
    """AC-011c: Digester サブクラス 2 個以上 → 終了コード 3 (絞れない)."""
    # Arrange
    module_file = tmp_path / "multi_digester.py"
    module_file.write_text("""\
from digestkit.digester import Digester
from digestkit.types import Item, Digest


class _Source:
    def fetch(self):
        return []


class _Extractor:
    def extract(self, item):
        return ""


class _Summarizer:
    def summarize(self, text, item):
        return Digest(summary="", tokens_in=0, tokens_out=0, latency_ms=0, model="stub")


class _Sink:
    def write(self, digest, item):
        pass


class DigestA(Digester):
    source = _Source()
    extractor = _Extractor()
    summarizer = _Summarizer()
    sink = _Sink()
    seen_store = None


class DigestB(Digester):
    source = _Source()
    extractor = _Extractor()
    summarizer = _Summarizer()
    sink = _Sink()
    seen_store = None
""")

    # Act
    exit_code = main(["run", str(module_file)])

    # Assert
    assert exit_code == 3


def test_cli_run_returns_one_on_partial_failure(tmp_path: Path) -> None:
    """AC-011d: 1 件失敗で他成功 → 終了コード 1 (部分失敗)."""
    # Arrange — 2 items; extractor fails on item "1" only
    module_file = tmp_path / "partial_fail.py"
    module_file.write_text("""\
from digestkit.digester import Digester
from digestkit.types import Item, Digest


class _Source:
    def fetch(self):
        return [Item(id="1", payload=None), Item(id="2", payload=None)]


class _Extractor:
    def extract(self, item):
        if item.id == "1":
            raise RuntimeError("extract failed")
        return f"text:{item.id}"


class _Summarizer:
    def summarize(self, text, item):
        return Digest(summary=text, tokens_in=1, tokens_out=1, latency_ms=0, model="stub")


class _Sink:
    def write(self, digest, item):
        pass


class MyDigester(Digester):
    source = _Source()
    extractor = _Extractor()
    summarizer = _Summarizer()
    sink = _Sink()
    seen_store = None
""")

    # Act
    exit_code = main(["run", str(module_file)])

    # Assert
    assert exit_code == 1


def test_cli_run_returns_two_on_total_failure(tmp_path: Path) -> None:
    """AC-011e: 全件失敗 → 終了コード 2."""
    # Arrange — extractor always raises
    module_file = tmp_path / "total_fail.py"
    module_file.write_text("""\
from digestkit.digester import Digester
from digestkit.types import Item, Digest


class _Source:
    def fetch(self):
        return [Item(id="1", payload=None), Item(id="2", payload=None)]


class _Extractor:
    def extract(self, item):
        raise RuntimeError("always fails")


class _Summarizer:
    def summarize(self, text, item):
        return Digest(summary=text, tokens_in=1, tokens_out=1, latency_ms=0, model="stub")


class _Sink:
    def write(self, digest, item):
        pass


class MyDigester(Digester):
    source = _Source()
    extractor = _Extractor()
    summarizer = _Summarizer()
    sink = _Sink()
    seen_store = None
""")

    # Act
    exit_code = main(["run", str(module_file)])

    # Assert
    assert exit_code == 2


def test_cli_run_dry_run_skips_sink_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-011f: --dry-run で Sink.write が呼ばれず RunResult.skipped == 件数."""
    # Arrange
    module_file = tmp_path / "dry_run.py"
    module_file.write_text(_VALID_DIGESTER_MODULE)

    # Act
    exit_code = main(["run", str(module_file), "--dry-run"])
    captured = capsys.readouterr()

    # Assert
    assert exit_code == 0
    assert "skipped=2" in captured.out
    assert "success=0" in captured.out


def test_cli_run_returns_three_on_syntax_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(review #5): 構文エラー Python ファイル → 終了コード 3 + stderr に SyntaxError."""
    # Arrange
    module_file = tmp_path / "syntax_error.py"
    module_file.write_text("def broken(\n    # unclosed parenthesis\n")

    # Act
    exit_code = main(["run", str(module_file)])
    captured = capsys.readouterr()

    # Assert
    assert exit_code == 3
    assert "SyntaxError" in captured.err
