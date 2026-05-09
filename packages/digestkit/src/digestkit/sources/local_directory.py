from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..types import Item


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
