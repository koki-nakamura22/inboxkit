"""AC-011 / AC-011a〜f: CLI ランナー (`digestkit run`)

実装ファイル: packages/digestkit/src/digestkit/cli.py
対応 SR: SR-F-007
"""

from __future__ import annotations

import pytest


def test_cli_run_executes_digester_and_returns_zero(tmp_path: object) -> None:
    """AC-011 正常系: 正しい Digester サブクラスを含む module を渡すと終了コード 0 + サマリ出力."""
    pytest.fail("not yet implemented")


def test_cli_run_returns_three_when_module_file_not_found() -> None:
    """AC-011a: ファイル不在 → 終了コード 3 + stderr メッセージ."""
    pytest.fail("not yet implemented")


def test_cli_run_returns_three_when_no_digester_subclass_found(tmp_path: object) -> None:
    """AC-011b: Digester サブクラスゼロ個 → 終了コード 3."""
    pytest.fail("not yet implemented")


def test_cli_run_returns_three_when_multiple_digester_subclasses_found(tmp_path: object) -> None:
    """AC-011c: Digester サブクラス 2 個以上 → 終了コード 3 (絞れない)."""
    pytest.fail("not yet implemented")


def test_cli_run_returns_one_on_partial_failure(tmp_path: object) -> None:
    """AC-011d: 1 件失敗で他成功 → 終了コード 1 (部分失敗)."""
    pytest.fail("not yet implemented")


def test_cli_run_returns_two_on_total_failure(tmp_path: object) -> None:
    """AC-011e: 全件失敗 → 終了コード 2."""
    pytest.fail("not yet implemented")


def test_cli_run_dry_run_skips_sink_writes(tmp_path: object) -> None:
    """AC-011f: --dry-run で Sink.write が呼ばれず RunResult.skipped == 件数."""
    pytest.fail("not yet implemented")
