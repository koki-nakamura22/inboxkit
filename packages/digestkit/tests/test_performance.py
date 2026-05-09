"""AC-P-001 / AC-P-002: Performance

実装ファイル: 横断 (Digester / Source / Sink すべて)
対応 SR: SR-P-002 / SR-P-003
"""

from __future__ import annotations

import pytest


@pytest.mark.slow
def test_framework_overhead_per_item_under_100ms() -> None:
    """AC-P-001: LLM mock + 10 件で 1 件あたり ≤ 100ms."""
    pytest.fail("not yet implemented")


@pytest.mark.slow
def test_run_completes_for_1000_items_under_memory_limit() -> None:
    """AC-P-002: 1,000 件処理. エラーなし完走 / メモリ ≤ 200MB / 所要時間 ≤ 100 秒."""
    pytest.fail("not yet implemented")
