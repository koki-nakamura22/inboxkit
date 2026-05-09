"""AC-002: 4 Protocol の構造的型適合 (`isinstance` チェック)

実装ファイル: packages/digestkit/src/digestkit/protocols.py
対応 SR: SR-F-002
"""

from __future__ import annotations

import pytest


def test_source_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Source Protocol が duck-typed クラスを isinstance で True と判定."""
    pytest.fail("not yet implemented")


def test_extractor_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Extractor Protocol が duck-typed クラスを isinstance で True と判定."""
    pytest.fail("not yet implemented")


def test_summarizer_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Summarizer Protocol が duck-typed クラスを isinstance で True と判定."""
    pytest.fail("not yet implemented")


def test_sink_protocol_runtime_checkable_with_duck_typed_class() -> None:
    """AC-002: Sink Protocol が duck-typed クラスを isinstance で True と判定."""
    pytest.fail("not yet implemented")


def test_protocol_isinstance_returns_false_when_method_is_missing() -> None:
    """AC-002: 必須メソッドを欠くクラスは isinstance で False."""
    pytest.fail("not yet implemented")
