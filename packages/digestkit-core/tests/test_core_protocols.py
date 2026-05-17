"""digestkit_core.protocols の smoke テスト."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from digestkit_core.protocols import Extractor, Source
from digestkit_core.types import Item


def test_source_protocol_is_importable() -> None:
    assert Source is not None


def test_extractor_protocol_is_importable() -> None:
    assert Extractor is not None


def test_source_protocol_structural_check() -> None:
    class MySource:
        def fetch(self) -> Iterable[Item]:
            return iter([])

    assert isinstance(MySource(), Source)


def test_extractor_protocol_structural_check() -> None:
    class MyExtractor:
        def extract(self, item: Item) -> str:
            return str(item.payload)

    assert isinstance(MyExtractor(), Extractor)


def test_source_and_extractor_are_distinct() -> None:
    assert Source is not Extractor


def test_item_dataclass_fields() -> None:
    import dataclasses

    fields = {f.name for f in dataclasses.fields(Item)}
    assert fields == {"id", "payload", "metadata"}


def test_item_is_frozen() -> None:
    import dataclasses

    item = Item(id="x", payload="y")
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.id = "z"  # type: ignore[misc]


def test_item_metadata_default_none() -> None:
    item = Item(id="a", payload=1)
    assert item.metadata is None
