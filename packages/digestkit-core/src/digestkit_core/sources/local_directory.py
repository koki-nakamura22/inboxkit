from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from digestkit_core.types import Item


class LocalDirectorySource:
    def __init__(self, path: Path | str, glob: str = "*") -> None:
        self._path = Path(path)
        self._glob = glob

    def fetch(self) -> Iterable[Item]:
        if not self._path.is_dir():
            return
        for p in sorted(self._path.glob(self._glob)):
            if p.is_file():
                yield Item(id=str(p.resolve()), payload=p)
