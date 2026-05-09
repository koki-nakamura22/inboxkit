"""Item / Digest dataclass の構築・immutability 検証

実装ファイル: packages/digestkit/src/digestkit/types.py
"""

from __future__ import annotations

import dataclasses

import pytest

from digestkit.types import Digest, Item


def test_item_fields_are_accessible_after_construction() -> None:
    """Item が id / payload フィールドを正しく保持する."""

    # Arrange
    item_id = "abc-123"
    payload = {"key": "value"}
    # Act
    item = Item(id=item_id, payload=payload)
    # Assert
    assert item.id == item_id
    assert item.payload == payload


def test_item_payload_accepts_arbitrary_type() -> None:
    """Item.payload は Any なので数値・文字列・None を受け付ける."""

    # Arrange / Act / Assert
    assert Item(id="int", payload=42).payload == 42
    assert Item(id="str", payload="hello").payload == "hello"
    assert Item(id="none", payload=None).payload is None


def test_item_is_frozen_raises_on_mutation() -> None:
    """Item は frozen=True なので属性の書き換えで FrozenInstanceError を送出する."""

    # Arrange
    item = Item(id="x", payload=0)
    # Act / Assert
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.id = "y"  # type: ignore[misc]


def test_digest_fields_are_accessible_after_construction() -> None:
    """Digest が全フィールドを正しく保持する."""

    # Arrange
    summary = "要約テキスト"
    tokens_in = 512
    tokens_out = 128
    latency_ms = 350
    model = "gpt-4o"
    # Act
    digest = Digest(
        summary=summary,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        model=model,
    )
    # Assert
    assert digest.summary == summary
    assert digest.tokens_in == tokens_in
    assert digest.tokens_out == tokens_out
    assert digest.latency_ms == latency_ms
    assert digest.model == model


def test_digest_is_frozen_raises_on_mutation() -> None:
    """Digest は frozen=True なので属性の書き換えで FrozenInstanceError を送出する."""

    # Arrange
    digest = Digest(summary="s", tokens_in=1, tokens_out=1, latency_ms=10, model="m")
    # Act / Assert
    with pytest.raises(dataclasses.FrozenInstanceError):
        digest.summary = "changed"  # type: ignore[misc]
