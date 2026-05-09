"""AC-001 / AC-001b / AC-001c / AC-R-001: Digester ABC の振る舞い

実装ファイル: packages/digestkit/src/digestkit/digester.py
対応 SR: SR-F-001 / SR-R-001
"""

from __future__ import annotations

import pytest


def test_digester_run_processes_all_items_in_order() -> None:
    """AC-001: Source.fetch -> Extractor.extract -> Summarizer.summarize -> Sink.write が順次実行され、3 件の Item で Sink.write が 3 回呼ばれる."""
    pytest.fail("not yet implemented")


def test_digester_run_returns_runresult_with_correct_counts() -> None:
    """AC-001: RunResult.success == 3 / failures == 0 / skipped == 0 が返る."""
    pytest.fail("not yet implemented")


@pytest.mark.parametrize(
    ("limit", "expected_processed"),
    [
        (0, 0),
        (1, 1),
        (3, 3),
        (5, 5),
        (6, 5),  # Source が 5 件しか返さないので min(limit, 5)
        (None, 5),
    ],
)
def test_digester_run_respects_limit_argument(limit: int | None, expected_processed: int) -> None:
    """AC-001b: limit 引数の境界値. Source 5 件返す状況で limit=N → 処理件数 == min(N, 5)."""
    pytest.fail("not yet implemented")


def test_digester_run_dry_run_skips_sink_write() -> None:
    """AC-011f 関連: dry_run=True で Sink.write が呼ばれず、RunResult.skipped == 件数."""
    pytest.fail("not yet implemented")


def test_digester_subclass_missing_source_raises_at_instantiation() -> None:
    """AC-001c: source 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    pytest.fail("not yet implemented")


def test_digester_subclass_missing_extractor_raises_at_instantiation() -> None:
    """AC-001c: extractor 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    pytest.fail("not yet implemented")


def test_digester_subclass_missing_summarizer_raises_at_instantiation() -> None:
    """AC-001c: summarizer 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    pytest.fail("not yet implemented")


def test_digester_subclass_missing_sink_raises_at_instantiation() -> None:
    """AC-001c: sink 属性を欠いた Digester サブクラスは __init__ で ConfigurationError."""
    pytest.fail("not yet implemented")


def test_digester_subclass_missing_all_raises_with_clear_message() -> None:
    """AC-001c: 全属性欠落時、例外メッセージに欠けている属性名すべてが含まれる."""
    pytest.fail("not yet implemented")


def test_digester_run_continues_after_single_item_extraction_failure() -> None:
    """AC-R-001: 5 件中 3 件目の Extractor が例外を投げても残りを処理. RunResult.success==4 / failures==1."""
    pytest.fail("not yet implemented")


def test_digester_run_failure_list_contains_failing_item() -> None:
    """AC-R-001: failures リストに失敗 Item の参照が含まれ、Sink.write は失敗 Item に対しては呼ばれない."""
    pytest.fail("not yet implemented")
