"""Lazy import smoke tests (Issue #2 再発防止).

`digestkit.sources` / `digestkit.sinks` の `__init__.py` は、optional extra に
依存するクラス (NotionDatabaseSource / SlackSink) を `__getattr__` で遅延 import
する。本テストは:

1. 親パッケージ import 直後、optional 依存のサブモジュールが sys.modules に
   ロードされていないこと (= eager import していない)
2. 名前にアクセスした時点で初めて当該サブモジュールがロードされること
3. 未知の属性は AttributeError を上げること

を検証する。サブプロセスでクリーンな import 状態を作って確認する。
"""

from __future__ import annotations

import subprocess
import sys
import textwrap


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_sources_does_not_eager_import_notion() -> None:
    """`from digestkit.sources import LocalDirectorySource` で notion_database が読まれない."""
    result = _run(
        """
        import sys
        from digestkit.sources import LocalDirectorySource  # noqa: F401

        assert "digestkit.sources.notion_database" not in sys.modules, (
            "notion_database should be lazy-loaded; got eager import"
        )
        """
    )
    assert result.returncode == 0, result.stderr


def test_sources_lazy_loads_notion_on_access() -> None:
    """`NotionDatabaseSource` を参照した時点で notion_database が読まれる."""
    result = _run(
        """
        import sys
        import digestkit.sources

        assert "digestkit.sources.notion_database" not in sys.modules
        cls = digestkit.sources.NotionDatabaseSource
        assert cls is not None
        assert "digestkit.sources.notion_database" in sys.modules
        """
    )
    assert result.returncode == 0, result.stderr


def test_sources_unknown_attribute_raises() -> None:
    import pytest

    import digestkit.sources

    with pytest.raises(AttributeError):
        _ = digestkit.sources.DoesNotExist  # type: ignore[attr-defined]


def test_sinks_does_not_eager_import_slack() -> None:
    """eager import される Sink (Email/SQLite/Composite) を取っても slack は読まれない."""
    result = _run(
        """
        import sys
        from digestkit.sinks import EmailSink, SQLiteSink, CompositeSink  # noqa: F401

        assert "digestkit.sinks.slack" not in sys.modules, (
            "slack should be lazy-loaded; got eager import"
        )
        """
    )
    assert result.returncode == 0, result.stderr


def test_sinks_lazy_loads_slack_on_access() -> None:
    result = _run(
        """
        import sys
        import digestkit.sinks

        assert "digestkit.sinks.slack" not in sys.modules
        cls = digestkit.sinks.SlackSink
        assert cls is not None
        assert "digestkit.sinks.slack" in sys.modules
        """
    )
    assert result.returncode == 0, result.stderr


def test_sinks_unknown_attribute_raises() -> None:
    import pytest

    import digestkit.sinks

    with pytest.raises(AttributeError):
        _ = digestkit.sinks.DoesNotExist  # type: ignore[attr-defined]
