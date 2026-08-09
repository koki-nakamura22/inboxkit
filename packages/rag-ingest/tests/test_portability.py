from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rag_ingest.exceptions import SqliteVecLoadError
from rag_ingest.sinks import SQLiteVecSink

# `spec=sqlite3.Connection` は使えない: 拡張ロード非対応でビルドされた
# インタプリタ (python.org / GitHub の macOS ビルド) には
# `enable_load_extension` 属性が無く、まさにこのテストが対象とする環境で
# spec がスタブを拒否して AttributeError になるため。属性を明示的に足した
# spec を渡し、どのインタプリタでも同じ形のモックになるようにする。
_CONNECTION_SPEC = [*dir(sqlite3.Connection), "enable_load_extension"]


def _mock_conn_raising_on_enable(exc: Exception) -> MagicMock:
    """Return a mock sqlite3.Connection whose enable_load_extension raises exc."""
    conn = MagicMock(spec=_CONNECTION_SPEC)
    conn.enable_load_extension.side_effect = exc
    return conn


def test_sqlite_vec_enable_load_extension_failure_raises(tmp_path: Path) -> None:
    """AC-Po-001: SqliteVecLoadError with install hint when enable_load_extension fails."""
    # Arrange: mock connection raises OperationalError on enable_load_extension
    db = tmp_path / "rag.db"
    mock_conn = _mock_conn_raising_on_enable(sqlite3.OperationalError("not authorized"))

    # Act
    with (
        patch("rag_ingest.sinks.sqlite_vec.sqlite3.connect", return_value=mock_conn),
        pytest.raises(SqliteVecLoadError) as exc_info,
    ):
        SQLiteVecSink(str(db), dim=4)

    # Assert: message contains install instructions and OS-specific hint
    msg = str(exc_info.value)
    assert "pip install sqlite-vec" in msg
    assert "Linux" in msg or "macOS" in msg


def test_sqlite_vec_load_failure_raises(tmp_path: Path) -> None:
    """SqliteVecLoadError with install hint when sqlite_vec.load fails after enable succeeds."""
    import rag_ingest.sinks.sqlite_vec as _module

    db = tmp_path / "rag.db"

    def fail_load(conn: object) -> None:
        raise Exception("no such module: vec0")

    with patch.object(_module, "sqlite_vec") as mock_sv:
        mock_sv.load.side_effect = fail_load
        with pytest.raises(SqliteVecLoadError) as exc_info:
            SQLiteVecSink(str(db), dim=4)

    msg = str(exc_info.value)
    assert "pip install sqlite-vec" in msg
    assert "Linux" in msg or "macOS" in msg
