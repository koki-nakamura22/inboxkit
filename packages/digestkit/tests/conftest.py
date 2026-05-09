"""共通 pytest 設定 + マーカー登録 (test-strategy.md §1.3 準拠)."""

from __future__ import annotations


def pytest_configure(config: object) -> None:
    """カスタムマーカー登録 (実体は pyproject.toml の [tool.pytest.ini_options] に書く想定)."""
    # NOTE: マーカー登録自体は pyproject.toml の markers 設定で十分。
    # 本 conftest.py は将来 fixtures を追加する時の入れ物。
    _ = config  # 未使用引数の警告抑止
