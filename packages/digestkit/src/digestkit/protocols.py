from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from digestkit.types import Digest, Item

if TYPE_CHECKING:
    # FailureInfo lives in digester.py which imports from this module; keep the
    # reference TYPE_CHECKING-only to avoid a runtime circular import.
    from digestkit.digester import FailureInfo


@runtime_checkable
class Source(Protocol):
    def fetch(self) -> Iterable[Item]: ...


@runtime_checkable
class AckSource(Protocol):
    """書き戻し対応の Source. Digester.run() は per_item で ack_success / ack_failure を呼ぶ.

    Issue #27. Source Protocol との継承関係を持たせると Protocol の structural
    subtyping で誤検知しやすいため、明示的に fetch も含めた独立 Protocol として宣言する.

    ack は per_item の "完了サイクル" にのみ対応する:
      - ``dry_run=True``: sink.write をスキップするため ack も呼ばない.
      - seen_store ヒット (= 過去に処理済み判定): Source 側は前回 run で既に
        ack 済みのはずで、呼び直さない.
      - dedup_key 計算失敗: ``stage='extract'`` として ack_failure を呼ぶ.

    Issue #28: Digester.ack_mode='after_run' を指定すると、run() ループ中は ack を
    呼ばずに成功/失敗を内部バッファに溜め、全 item 処理後にまとめて
    ack_success / ack_failure を順次呼ぶ. dry_run / seen_store ヒット時に ack を
    呼ばない方針は per_item と同じ.
    """

    def fetch(self) -> Iterable[Item]: ...

    def ack_success(self, item: Item, digest: Digest) -> None: ...

    def ack_failure(self, failure: FailureInfo) -> None: ...


@runtime_checkable
class Extractor(Protocol):
    def extract(self, item: Item) -> str: ...


@runtime_checkable
class Summarizer(Protocol):
    def summarize(self, text: str, item: Item) -> Digest: ...


@runtime_checkable
class Sink(Protocol):
    def write(self, digest: Digest, item: Item) -> None: ...
