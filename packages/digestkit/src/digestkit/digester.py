from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, final

from digestkit.dedup import SeenStore, SQLiteSeenStore, default_seen_store_path, item_id_key
from digestkit.protocols import AckSource, Extractor, Sink, Source, Summarizer
from digestkit.types import Digest, Item
from digestkit_core.types import (
    ConfigurationError as ConfigurationError,  # re-export (canonical: digestkit_core)
)
from digestkit_core.types import (
    FailureInfo as FailureInfo,  # re-export (canonical: digestkit_core)
)
from digestkit_core.types import (
    FailureStage as FailureStage,  # re-export (canonical: digestkit_core)
)

__all__ = [
    "AckMode",
    "ConfigurationError",
    "DedupKeyFn",
    "Digester",
    "FailureInfo",
    "FailureStage",
    "RunResult",
]

logger = logging.getLogger(__name__)

_REQUIRED_ATTRS = ("source", "extractor", "summarizer", "sink")

DedupKeyFn = Callable[[Item], str]


@final
class _SeenStoreSentinel:
    """Sentinel distinguishing "not provided" from explicit None in Digester.__init__."""


_SEEN_STORE_UNSET = _SeenStoreSentinel()


@final
class _DedupKeySentinel:
    """Sentinel distinguishing "not provided" from explicit None in Digester.__init__."""


_DEDUP_KEY_UNSET = _DedupKeySentinel()


@final
class _AckModeSentinel:
    """Sentinel distinguishing "not provided" from explicit value in Digester.__init__."""


_ACK_MODE_UNSET = _AckModeSentinel()

AckMode = Literal["per_item", "after_run"]


@dataclass
class RunResult:
    success: int = 0
    skipped: int = 0
    failures: list[FailureInfo] = field(default_factory=lambda: [])


class Digester:
    source: Source
    extractor: Extractor
    summarizer: Summarizer
    sink: Sink
    # Subclasses may override: seen_store: SeenStore | None = <value>
    # If not overridden, __init__ creates the default SQLiteSeenStore.
    # Set seen_store = None in a subclass or pass seen_store=None to disable dedup.

    # Issue #12: dedup キー戦略の差し替えポイント.
    # Subclasses may override: dedup_key: DedupKeyFn = <fn>
    # 既定は ``item_id_key`` (= ``Item.id`` をそのまま使う後方互換挙動).
    # 内容ハッシュで dedup したい場合は ``digestkit.dedup.content_sha256_key``
    # を指定するか、独自の ``Callable[[Item], str]`` を渡す.

    # Issue #13: コア 4 依存 (source/extractor/summarizer/sink) もコンストラクタ
    # kwarg で受け取れるようにする (constructor injection). サブクラス class
    # 属性を kwarg が override する (seen_store/dedup_key と同じハイブリッド
    # パターン). factory method ではなく __init__ のシグネチャ拡張.

    # Issue #28: ack タイミング戦略. ``per_item`` は #27 既定挙動 (各 item の
    # sink.write 直後に ack). ``after_run`` は全 item 処理後に成功/失敗をまとめて
    # ack する (read-later-digest 等の「全通知成功後に書き戻し」用途).
    #
    # ``after_run`` の注意点:
    #   - run() が完走した時のみ ack を発行する. ループ途中で
    #     ``KeyboardInterrupt`` 等の外部例外で抜けた場合、バッファ済み ack は
    #     発行されないまま破棄される (= 未 ack 扱い. 次回 run で再処理させる前提).
    #   - run() 完了までバッファに (Item, Digest) と FailureInfo を保持するため、
    #     ``Source.fetch()`` がジェネレータで遅延評価される場合でも after_run 時は
    #     全件分のメモリを消費する. 数万件級のストリーミング処理で利用する場合は
    #     ``per_item`` を選ぶか、Source 側でバッチ分割すること.
    ack_mode: AckMode = "per_item"

    def __init__(
        self,
        *,
        source: Source | None = None,
        extractor: Extractor | None = None,
        summarizer: Summarizer | None = None,
        sink: Sink | None = None,
        seen_store: SeenStore | None | _SeenStoreSentinel = _SEEN_STORE_UNSET,
        dedup_key: DedupKeyFn | _DedupKeySentinel = _DEDUP_KEY_UNSET,
        ack_mode: AckMode | _AckModeSentinel = _ACK_MODE_UNSET,
    ) -> None:
        # kwarg が渡されたものはインスタンス属性として設定 (class 属性を override).
        # None のまま渡された場合は「未指定」扱いで、class 属性があればそれを使う.
        if source is not None:
            self.source = source
        if extractor is not None:
            self.extractor = extractor
        if summarizer is not None:
            self.summarizer = summarizer
        if sink is not None:
            self.sink = sink

        missing = [a for a in _REQUIRED_ATTRS if not hasattr(self, a)]
        if missing:
            raise ConfigurationError(f"Missing required attributes: {missing}")

        if not isinstance(seen_store, _SeenStoreSentinel):
            self.seen_store: SeenStore | None = seen_store
        elif not hasattr(self, "seen_store"):
            self.seen_store = SQLiteSeenStore(default_seen_store_path(type(self).__name__))
        # else: subclass defined seen_store as class attribute; leave it as-is

        if not isinstance(dedup_key, _DedupKeySentinel):
            self.dedup_key: DedupKeyFn = dedup_key
        elif not hasattr(self, "dedup_key"):
            self.dedup_key = item_id_key
        # else: subclass defined dedup_key as class attribute; leave it as-is

        if not isinstance(ack_mode, _AckModeSentinel):
            self.ack_mode = ack_mode

    def run(
        self,
        limit: int | None = None,
        dry_run: bool = False,
        *,
        length: str | None = None,
    ) -> RunResult:
        """パイプラインを実行する.

        Args:
            limit: 処理件数の上限.
            dry_run: True なら sink への書き込みと SeenStore 更新をスキップ.
            length: 段階別要約に対応する Summarizer
                (例: :class:`digestkit.summarizers.LLMSummarizer` で
                ``prompts`` を指定したもの) に渡す要約長キー.
                None なら summarizer に length 引数を渡さず呼び出すため、
                Summarizer Protocol だけを満たすカスタム実装でも従来どおり
                動作する.

        Notes:
            Issue #32: sink.write 成功後の帳簿更新失敗の扱い.
              ``sink.write`` が成功した時点で副作用 (Slack 通知 / メール送信 /
              Notion ページ書き込み 等) は既に外部に出ている. その後の
              ``seen_store.add`` が失敗しても、これを ``ack_failure(stage="write")``
              に降格させると source 側 (例: NotionDatabaseSource の Status 書き戻し)
              が「失敗」となり、次回 run で再処理 = 副作用の二重発行を招く.
              そこで以下の契約を採用する:

              - ``sink.write`` の失敗のみが ``FailureInfo(stage="write")`` と
                ``ack_failure`` を発生させる.
              - ``sink.write`` 成功直後に ``result.success`` を加算する
                (帳簿更新の成否に依存しない).
              - ``seen_store.add`` 失敗は warning ログのみで握りつぶす. その item は
                次回 run で再処理対象になる可能性があるが、source 側 dedup
                (例: Notion DB Status フィルタ) が機能していれば実害は出ない.
              - ``ack_success`` は ``seen_store.add`` の成否に関わらず発行する.
        """
        result = RunResult()
        items = self.source.fetch()
        processed = 0
        # Issue #27 / #28: 書き戻し対応 Source なら ack を呼ぶ. ack_mode により
        # per_item (即時) / after_run (run 完走後に一括) を切り替える.
        ack_source: AckSource | None = self.source if isinstance(self.source, AckSource) else None
        defer_ack = ack_source is not None and self.ack_mode == "after_run"
        pending_successes: list[tuple[Item, Digest]] = []
        pending_failures: list[FailureInfo] = []

        def _ack_success(item: Item, digest: Digest) -> None:
            if ack_source is None:
                return
            if defer_ack:
                pending_successes.append((item, digest))
                return
            try:
                ack_source.ack_success(item, digest)
            except Exception as exc:
                logger.warning("ack_success failed for item %s: %s", item.id, exc)

        def _ack_failure(failure: FailureInfo) -> None:
            if ack_source is None:
                return
            if defer_ack:
                pending_failures.append(failure)
                return
            try:
                ack_source.ack_failure(failure)
            except Exception as exc:
                logger.warning("ack_failure failed for item %s: %s", failure.item.id, exc)

        for item in items:
            if limit is not None and processed >= limit:
                break

            # Issue #12: dedup キーは ``self.dedup_key`` で計算する
            # (既定では ``item.id``). キー計算自体の例外は extract と同様、
            # 該当 Item のみを失敗扱いにして処理は継続する.
            dedup_key_value: str | None = None
            if not dry_run and self.seen_store is not None:
                try:
                    dedup_key_value = self.dedup_key(item)
                except Exception as exc:
                    logger.warning("dedup_key failed for item %s: %s", item.id, exc)
                    failure = FailureInfo(item=item, stage="extract", error=exc)
                    result.failures.append(failure)
                    _ack_failure(failure)
                    processed += 1
                    continue
                if self.seen_store.has(dedup_key_value):
                    result.skipped += 1
                    processed += 1
                    continue

            try:
                text = self.extractor.extract(item)
            except Exception as exc:
                logger.warning("extract failed for item %s: %s", item.id, exc)
                failure = FailureInfo(item=item, stage="extract", error=exc)
                result.failures.append(failure)
                _ack_failure(failure)
                processed += 1
                continue

            try:
                # length が None の時は kw を渡さず呼び出し、
                # Summarizer Protocol を満たすだけのカスタム実装も壊さない.
                if length is None:
                    digest = self.summarizer.summarize(text, item)
                else:
                    # length kw は LLMSummarizer 等の拡張実装のみが受ける
                    # (Protocol には含まれない). ここは型システムが知らない
                    # ダックタイピング呼び出しなので Any 経由で逃がす.
                    summarizer_with_length: Any = self.summarizer
                    digest = summarizer_with_length.summarize(text, item, length=length)
            except Exception as exc:
                logger.warning("summarize failed for item %s: %s", item.id, exc)
                failure = FailureInfo(item=item, stage="summarize", error=exc)
                result.failures.append(failure)
                _ack_failure(failure)
                processed += 1
                continue

            if dry_run:
                result.skipped += 1
            else:
                # Issue #32: sink.write の成功/失敗と、その後の帳簿更新
                # (seen_store.add) の失敗を混同しない. 旧実装では同じ try で守って
                # いたため、Slack 通知済み / Notion ページ書き込み済み等の副作用が
                # 既に外に出ているにも関わらず seen_store.add の例外で
                # ack_failure(stage="write") が呼ばれ、source 側の状態が不整合に
                # なる (例: Notion DB Status が「失敗」に書き戻され、次回再処理で
                # 二重送信) 問題があった. ここでは:
                #   1) sink.write のみを try で守り、失敗時のみ stage="write"
                #   2) success カウントは sink.write 成功直後にインクリメント
                #   3) seen_store.add 失敗は warning ログのみ (副作用は巻き戻せない
                #      ため ack_failure には降格させない. 次回 run で再処理される
                #      可能性は残るが、ack_success 側で source 自身の dedup
                #      (Notion DB Status 等) が効くケースが多い)
                #   4) ack_success は seen_store.add の成否に関わらず発行する
                try:
                    self.sink.write(digest, item)
                except Exception as exc:
                    logger.warning("sink.write failed for item %s: %s", item.id, exc)
                    failure = FailureInfo(item=item, stage="write", error=exc)
                    result.failures.append(failure)
                    _ack_failure(failure)
                    processed += 1
                    continue

                result.success += 1

                if self.seen_store is not None:
                    # dedup_key_value は dry_run=False かつ seen_store!=None の
                    # この分岐に来る時点で必ず計算済み (skip 判定で同じキーを使う).
                    assert dedup_key_value is not None
                    try:
                        self.seen_store.add(dedup_key_value)
                    except Exception as exc:
                        logger.warning(
                            "seen_store.add failed after successful sink.write "
                            "for item %s: %s "
                            "(sink side effects already applied; item may be "
                            "re-processed on next run if source-side dedup "
                            "does not catch it)",
                            item.id,
                            exc,
                        )

                _ack_success(item, digest)

            processed += 1

        # Issue #28: after_run モードでは run 完走後にバッファした ack を順次発行する.
        # ack 自体の失敗は per_item と同じく warning + 継続 (1 件失敗で残りを止めない).
        if defer_ack and ack_source is not None:
            for item, digest in pending_successes:
                try:
                    ack_source.ack_success(item, digest)
                except Exception as exc:
                    logger.warning("ack_success failed for item %s: %s", item.id, exc)
            for failure in pending_failures:
                try:
                    ack_source.ack_failure(failure)
                except Exception as exc:
                    logger.warning("ack_failure failed for item %s: %s", failure.item.id, exc)

        logger.info(
            "run complete: success=%d skipped=%d failures=%d",
            result.success,
            result.skipped,
            len(result.failures),
        )
        return result
