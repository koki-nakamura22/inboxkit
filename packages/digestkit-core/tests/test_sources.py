"""digestkit_core.sources の smoke テスト."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from digestkit_core.sources import LocalDirectorySource, NotionDatabaseSource
from digestkit_core.sources.local_directory import (
    LocalDirectorySource as LocalDirectorySourceDirect,
)
from digestkit_core.types import ConfigurationError, Item


def test_local_directory_source_importable() -> None:
    assert LocalDirectorySource is not None


def test_local_directory_source_canonical() -> None:
    assert LocalDirectorySource is LocalDirectorySourceDirect


def test_local_directory_source_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        source = LocalDirectorySource(tmpdir)
        items = list(source.fetch())
        assert items == []


def test_local_directory_source_with_files() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "a.txt").write_text("hello")
        (p / "b.txt").write_text("world")
        source = LocalDirectorySource(tmpdir)
        items = list(source.fetch())
        assert len(items) == 2
        assert all(isinstance(i, Item) for i in items)
        assert all(isinstance(i.payload, Path) for i in items)


def test_local_directory_source_glob_filter() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "a.txt").write_text("a")
        (p / "b.md").write_text("b")
        source = LocalDirectorySource(tmpdir, glob="*.txt")
        items = list(source.fetch())
        assert len(items) == 1
        assert items[0].payload.suffix == ".txt"


def test_local_directory_source_nonexistent_dir() -> None:
    source = LocalDirectorySource("/nonexistent/path/xyz123")
    items = list(source.fetch())
    assert items == []


def test_local_directory_source_item_id_is_absolute() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "test.txt").write_text("content")
        source = LocalDirectorySource(tmpdir)
        items = list(source.fetch())
        assert len(items) == 1
        assert Path(items[0].id).is_absolute()


def test_notion_database_source_importable() -> None:
    assert NotionDatabaseSource is not None


def test_notion_database_source_requires_token() -> None:
    env_backup = os.environ.pop("NOTION_TOKEN", None)
    try:
        with pytest.raises(ConfigurationError, match="token"):
            NotionDatabaseSource(database_id="test-db")
    finally:
        if env_backup is not None:
            os.environ["NOTION_TOKEN"] = env_backup


def test_notion_database_source_invalid_max_retries() -> None:
    with pytest.raises(ConfigurationError, match="max_retries"):
        NotionDatabaseSource(database_id="test-db", token="tok", max_retries=-1)


def test_notion_database_source_invalid_backoff() -> None:
    with pytest.raises(ConfigurationError, match="initial_backoff_sec"):
        NotionDatabaseSource(database_id="test-db", token="tok", initial_backoff_sec=-1.0)


def test_notion_database_source_status_without_value() -> None:
    with pytest.raises(ConfigurationError):
        NotionDatabaseSource(
            database_id="test-db",
            token="tok",
            status_property="Status",
        )


def test_notion_database_source_status_value_without_property() -> None:
    with pytest.raises(ConfigurationError):
        NotionDatabaseSource(
            database_id="test-db",
            token="tok",
            status_value_success="Done",
        )
