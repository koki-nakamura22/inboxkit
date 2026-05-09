"""AC-004: LocalDirectorySource

実装ファイル: packages/digestkit/src/digestkit/sources/local_directory.py
対応 SR: SR-F-004 (Source)
"""

from __future__ import annotations

import pytest


def test_local_directory_source_yields_matching_files(tmp_path: object) -> None:
    """AC-004: tmp に a.pdf / b.pdf / c.txt 配置 → glob='*.pdf' で 2 件 yield."""
    pytest.fail("not yet implemented")


def test_local_directory_source_excludes_non_matching_glob(tmp_path: object) -> None:
    """AC-004: c.txt は yield されない."""
    pytest.fail("not yet implemented")


def test_local_directory_source_returns_empty_for_empty_directory(tmp_path: object) -> None:
    """AC-004 境界値: 空ディレクトリで 0 件 yield."""
    pytest.fail("not yet implemented")


def test_local_directory_source_returns_empty_for_no_glob_match(tmp_path: object) -> None:
    """AC-004 境界値: glob 不一致で 0 件 yield."""
    pytest.fail("not yet implemented")


def test_local_directory_source_item_id_is_unique_per_path(tmp_path: object) -> None:
    """AC-004: Item.id がパスベースで一意."""
    pytest.fail("not yet implemented")
