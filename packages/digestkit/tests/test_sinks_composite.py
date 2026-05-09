"""AC-013: CompositeSink

実装ファイル: packages/digestkit/src/digestkit/sinks/composite.py
対応 SR: SR-F-010 / SR-R-001
"""

from __future__ import annotations

import pytest


def test_composite_sink_calls_all_inner_sinks_in_order() -> None:
    """AC-013: A + B + C の順で write 呼び出し."""
    pytest.fail("not yet implemented")


def test_composite_sink_continues_after_inner_sink_failure() -> None:
    """AC-013: 中央 Sink (B) が失敗しても A と C は呼ばれる."""
    pytest.fail("not yet implemented")


def test_composite_sink_raises_aggregated_error_when_inner_fails() -> None:
    """AC-013: B の例外が CompositeSinkError として集約送出される."""
    pytest.fail("not yet implemented")


def test_composite_sink_aggregated_error_contains_inner_exception() -> None:
    """AC-013: CompositeSinkError に B のエラー情報が含まれる."""
    pytest.fail("not yet implemented")
