"""AC-004: LocalDirectorySource

実装ファイル: packages/digestkit/src/digestkit/sources/local_directory.py
対応 SR: SR-F-004 (Source)
"""

from __future__ import annotations

from pathlib import Path

from digestkit.sources.local_directory import LocalDirectorySource
from digestkit.types import Item


def test_local_directory_source_yields_matching_files(tmp_path: Path) -> None:
    """AC-004: tmp に a.pdf / b.pdf / c.txt 配置 → glob='*.pdf' で 2 件 yield."""
    # Arrange
    (tmp_path / "a.pdf").write_text("a")
    (tmp_path / "b.pdf").write_text("b")
    (tmp_path / "c.txt").write_text("c")
    source = LocalDirectorySource(tmp_path, glob="*.pdf")

    # Act
    items = list(source.fetch())

    # Assert
    assert len(items) == 2
    yielded_names = {Path(item.payload).name for item in items}
    assert yielded_names == {"a.pdf", "b.pdf"}


def test_local_directory_source_excludes_non_matching_glob(tmp_path: Path) -> None:
    """AC-004: c.txt は yield されない (a.pdf のみ 1 件取得される)."""
    # Arrange
    (tmp_path / "a.pdf").write_text("a")
    (tmp_path / "c.txt").write_text("c")
    source = LocalDirectorySource(tmp_path, glob="*.pdf")

    # Act
    items = list(source.fetch())

    # Assert
    assert len(items) == 1
    assert {Path(item.payload).name for item in items} == {"a.pdf"}


def test_local_directory_source_returns_empty_for_empty_directory(tmp_path: Path) -> None:
    """AC-004 境界値: 空ディレクトリで 0 件 yield."""
    # Arrange
    source = LocalDirectorySource(tmp_path)

    # Act
    items = list(source.fetch())

    # Assert
    assert items == []


def test_local_directory_source_returns_empty_for_no_glob_match(tmp_path: Path) -> None:
    """AC-004 境界値: glob 不一致で 0 件 yield."""
    # Arrange
    (tmp_path / "a.txt").write_text("a")
    source = LocalDirectorySource(tmp_path, glob="*.pdf")

    # Act
    items = list(source.fetch())

    # Assert
    assert items == []


def test_local_directory_source_item_id_is_unique_per_path(tmp_path: Path) -> None:
    """AC-004: Item.id がパスベースで一意 (str(path.resolve()))."""
    # Arrange
    (tmp_path / "a.pdf").write_text("a")
    (tmp_path / "b.pdf").write_text("b")
    source = LocalDirectorySource(tmp_path, glob="*.pdf")

    # Act
    items = list(source.fetch())

    # Assert — ID が絶対パス文字列と一致し、重複がない
    expected_ids = {
        str((tmp_path / "a.pdf").resolve()),
        str((tmp_path / "b.pdf").resolve()),
    }
    assert {item.id for item in items} == expected_ids


def test_local_directory_source_returns_empty_for_nonexistent_directory() -> None:
    """D-101: 存在しないディレクトリを渡した場合も空 Iterable を返す (例外を投げない)."""
    # Arrange
    source = LocalDirectorySource("/nonexistent/path/that/does/not/exist")

    # Act
    items = list(source.fetch())

    # Assert
    assert items == []


def test_local_directory_source_items_are_item_instances(tmp_path: Path) -> None:
    """fetch() が返す各要素が Item 型である."""
    # Arrange
    (tmp_path / "x.pdf").write_text("x")
    source = LocalDirectorySource(tmp_path, glob="*.pdf")

    # Act
    items = list(source.fetch())

    # Assert
    assert len(items) == 1
    assert isinstance(items[0], Item)


def test_local_directory_source_payload_is_path_instance(tmp_path: Path) -> None:
    """Item.payload が Path インスタンスである."""
    # Arrange
    (tmp_path / "x.pdf").write_text("x")
    source = LocalDirectorySource(tmp_path, glob="*.pdf")

    # Act
    items = list(source.fetch())

    # Assert
    assert isinstance(items[0].payload, Path)


def test_local_directory_source_accepts_string_path(tmp_path: Path) -> None:
    """path 引数に str を渡しても動作する."""
    # Arrange
    (tmp_path / "a.txt").write_text("a")
    source = LocalDirectorySource(str(tmp_path))

    # Act
    items = list(source.fetch())

    # Assert
    assert len(items) == 1


def test_local_directory_source_skips_subdirectories(tmp_path: Path) -> None:
    """サブディレクトリは yield されない (is_file() チェック)."""
    # Arrange
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (tmp_path / "a.txt").write_text("a")
    source = LocalDirectorySource(tmp_path, glob="*")

    # Act
    items = list(source.fetch())

    # Assert — ファイル 1 件のみ取得され、サブディレクトリは含まれない
    assert len(items) == 1
    assert Path(items[0].payload).is_file()
    assert Path(items[0].payload).name == "a.txt"
