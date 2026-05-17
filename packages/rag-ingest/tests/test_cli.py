"""CLI tests: AC-008 / AC-008b / AC-008c."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from rag_ingest.cli import cli

# ---------------------------------------------------------------------------
# Module template helpers
# ---------------------------------------------------------------------------

_STUB_CLASSES = """\
from __future__ import annotations
from collections.abc import Iterable
from typing import Any
from rag_ingest import Ingester, Chunk
from rag_ingest._upstream import Item


class _Source:
    def __init__(self, n: int) -> None:
        self._n = n

    def fetch(self) -> Iterable[Item]:
        for i in range(self._n):
            yield Item(id=f"item-{i}", payload=f"text-{i}")


class _Extractor:
    def extract(self, item: Item) -> str:
        return str(item.payload)


class _ExtractorPartialFail:
    def extract(self, item: Item) -> str:
        if item.id == "item-0":
            raise RuntimeError("forced failure")
        return str(item.payload)


class _ExtractorAllFail:
    def extract(self, item: Item) -> str:
        raise RuntimeError("always fails")


class _Chunker:
    @property
    def config(self) -> dict[str, Any]:
        return {}

    def chunk(self, text: str, item: Item) -> list[Chunk]:
        return [Chunk(text=text, chunk_index=0)]


class _Embedder:
    @property
    def provider(self) -> str:
        return "stub"

    @property
    def model(self) -> str:
        return "stub"

    def embed(self, chunks: list[Chunk]) -> list[list[float]]:
        return [[0.1] for _ in chunks]

    def dim(self) -> int:
        return 1


class _Sink:
    def write(self, chunks: Any, vectors: Any, item: Any, ctx: Any) -> None:
        pass

    def existing_source_uris(self) -> set[str]:
        return set()


class _PreloadedSink:
    def write(self, chunks: Any, vectors: Any, item: Any, ctx: Any) -> None:
        pass

    def existing_source_uris(self) -> set[str]:
        return {"item-0", "item-1"}

"""


def _write_basic(tmp_path: Path, n: int = 3) -> Path:
    code = (
        _STUB_CLASSES
        + f"""\
class MyIngester(Ingester):
    def __init__(self) -> None:
        self.source = _Source({n})
        self.extractor = _Extractor()
        self.chunker = _Chunker()
        self.embedder = _Embedder()
        self.sink = _Sink()
"""
    )
    p = tmp_path / "my_ingester.py"
    p.write_text(code)
    return p


def _write_partial_fail(tmp_path: Path) -> Path:
    code = (
        _STUB_CLASSES
        + """\
class MyIngester(Ingester):
    def __init__(self) -> None:
        self.source = _Source(3)
        self.extractor = _ExtractorPartialFail()
        self.chunker = _Chunker()
        self.embedder = _Embedder()
        self.sink = _Sink()
"""
    )
    p = tmp_path / "my_ingester.py"
    p.write_text(code)
    return p


def _write_all_fail(tmp_path: Path) -> Path:
    code = (
        _STUB_CLASSES
        + """\
class MyIngester(Ingester):
    def __init__(self) -> None:
        self.source = _Source(3)
        self.extractor = _ExtractorAllFail()
        self.chunker = _Chunker()
        self.embedder = _Embedder()
        self.sink = _Sink()
"""
    )
    p = tmp_path / "my_ingester.py"
    p.write_text(code)
    return p


def _write_no_subclass(tmp_path: Path) -> Path:
    code = "class Foo:\n    pass\n"
    p = tmp_path / "my_ingester.py"
    p.write_text(code)
    return p


def _write_no_attrs_subclass(tmp_path: Path) -> Path:
    """Module with Ingester subclass that has no required attrs (→ ConfigurationError)."""
    code = (
        _STUB_CLASSES
        + """\
class MyIngester(Ingester):
    pass  # no source/extractor/chunker/embedder/sink → ConfigurationError
"""
    )
    p = tmp_path / "my_ingester.py"
    p.write_text(code)
    return p


def _write_multi_subclass(tmp_path: Path) -> Path:
    code = (
        _STUB_CLASSES
        + """\
class IngesterA(Ingester):
    def __init__(self) -> None:
        self.source = _Source(1)
        self.extractor = _Extractor()
        self.chunker = _Chunker()
        self.embedder = _Embedder()
        self.sink = _Sink()


class IngesterB(Ingester):
    def __init__(self) -> None:
        self.source = _Source(1)
        self.extractor = _Extractor()
        self.chunker = _Chunker()
        self.embedder = _Embedder()
        self.sink = _Sink()
"""
    )
    p = tmp_path / "my_ingester.py"
    p.write_text(code)
    return p


def _write_preloaded(tmp_path: Path) -> Path:
    code = (
        _STUB_CLASSES
        + """\
class MyIngester(Ingester):
    def __init__(self) -> None:
        self.source = _Source(3)
        self.extractor = _Extractor()
        self.chunker = _Chunker()
        self.embedder = _Embedder()
        self.sink = _PreloadedSink()
"""
    )
    p = tmp_path / "my_ingester.py"
    p.write_text(code)
    return p


# ---------------------------------------------------------------------------
# AC-008: basic run
# ---------------------------------------------------------------------------


def test_cli_run_basic_exit_code_zero(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(_write_basic(tmp_path))])
    assert result.exit_code == 0


def test_cli_run_basic_summary_in_stdout(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(_write_basic(tmp_path))])
    assert "processed=3" in result.output
    assert "skipped=0" in result.output
    assert "failures=0" in result.output


def test_cli_run_basic_chunks_in_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(_write_basic(tmp_path))])
    assert "chunks=3" in result.output


# ---------------------------------------------------------------------------
# AC-008b: exit code branches
# ---------------------------------------------------------------------------


def test_cli_run_configuration_error_exit_3(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_no_attrs_subclass(tmp_path))])
    assert result.exit_code == 3


def test_cli_run_partial_failure_exit_1(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_partial_fail(tmp_path))])
    assert result.exit_code == 1


def test_cli_run_partial_failure_summary(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_partial_fail(tmp_path))])
    assert "processed=2" in result.output
    assert "failures=1" in result.output


def test_cli_run_all_failure_exit_2(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_all_fail(tmp_path))])
    assert result.exit_code == 2


def test_cli_run_all_failure_summary(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_all_fail(tmp_path))])
    assert "processed=0" in result.output
    assert "failures=3" in result.output


def test_cli_run_no_subclass_exit_3(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_no_subclass(tmp_path))])
    assert result.exit_code == 3


def test_cli_run_multiple_subclasses_exit_3(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_multi_subclass(tmp_path))])
    assert result.exit_code == 3


# ---------------------------------------------------------------------------
# AC-008c: --dry-run / --force / --limit
# ---------------------------------------------------------------------------


def test_cli_dry_run_exit_code_zero(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_basic(tmp_path)), "--dry-run"])
    assert result.exit_code == 0


def test_cli_dry_run_shows_dry_run_chunks(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_basic(tmp_path)), "--dry-run"])
    assert "processed=0" in result.output
    assert "dry_run_chunks=3" in result.output


def test_cli_dry_run_no_chunks_written(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_basic(tmp_path)), "--dry-run"])
    assert "chunks=0" in result.output


def test_cli_without_force_skips_existing_uris(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_preloaded(tmp_path))])
    assert result.exit_code == 0
    assert "processed=1" in result.output
    assert "skipped=2" in result.output


def test_cli_force_processes_all_despite_existing_uris(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_preloaded(tmp_path)), "--force"])
    assert result.exit_code == 0
    assert "processed=3" in result.output
    assert "skipped=0" in result.output


def test_cli_limit_restricts_items(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_basic(tmp_path, n=5)), "--limit", "2"])
    assert result.exit_code == 0
    assert "processed=2" in result.output


def test_cli_limit_zero_processes_nothing(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_basic(tmp_path)), "--limit", "0"])
    assert result.exit_code == 0
    assert "processed=0" in result.output


def test_cli_limit_larger_than_item_count_processes_all(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run", str(_write_basic(tmp_path, n=3)), "--limit", "100"])
    assert result.exit_code == 0
    assert "processed=3" in result.output
