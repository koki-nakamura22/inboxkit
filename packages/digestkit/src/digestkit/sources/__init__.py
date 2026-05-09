"""Source 実装の re-export.

`NotionDatabaseSource` は `notion` extra (`notion-client`) を要求するため、
パッケージ初期化時に eager import すると `digestkit[pdf]` 等の他 extra
ユーザーが巻き込まれて壊れる (Issue #2)。PEP 562 `__getattr__` で遅延 import し、
`from digestkit.sources import NotionDatabaseSource` 実行時にだけ依存を要求する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .local_directory import LocalDirectorySource

if TYPE_CHECKING:
    from .notion_database import NotionDatabaseSource

__all__ = ["LocalDirectorySource", "NotionDatabaseSource"]


def __getattr__(name: str) -> Any:
    if name == "NotionDatabaseSource":
        from .notion_database import NotionDatabaseSource

        return NotionDatabaseSource
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
