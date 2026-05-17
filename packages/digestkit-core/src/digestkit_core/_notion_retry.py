"""Notion API 呼び出し用の 429 rate-limit retry helper (Issue #42).

``NotionDatabaseSource`` / ``NotionPageSink`` から共通利用される. 採用案は
ISSUE 本文の案 A (各クラスに ``max_retries`` / ``initial_backoff_sec`` を生やす)
で、実装の重複を避けるため retry 本体だけを本モジュールに分離する.

セマンティクス:
  - 429 (``APIResponseError.status == 429``) を受けた場合のみ retry する.
  - ``Retry-After`` ヘッダがあればその秒数 (整数 / HTTP date 両対応) を sleep する.
    無ければ exponential backoff (``initial_backoff_sec * 2 ** attempt``) を使う.
  - ``max_retries`` を超えたら最後の例外をそのまま re-raise する.
  - 429 以外の例外は retry せず即時 re-raise する (現状挙動を保つ).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import TypeVar

from notion_client.errors import APIResponseError

T = TypeVar("T")


def _parse_retry_after(value: str) -> float | None:
    """``Retry-After`` ヘッダ値を秒数に変換する.

    秒数 (整数 / 小数) または HTTP date 形式の双方を受け付ける. パースできない場合は
    ``None`` を返し、呼び出し側で exponential backoff へ fallback させる.
    """
    value = value.strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    now = time.time()
    target = dt.timestamp()
    return max(0.0, target - now)


def with_retry(
    func: Callable[[], T],
    *,
    max_retries: int,
    initial_backoff_sec: float,
    sleep: Callable[[float], None] | None = None,
) -> T:
    """``func`` を呼び出し、429 が出たら指数バックオフで最大 ``max_retries`` 回 retry する.

    ``max_retries=0`` の場合は retry なしで 1 度だけ呼ぶ (= ``func()`` と等価).
    ``sleep`` 未指定時は ``time.sleep`` を呼び出し時に解決する (テストで monkeypatch
    可能にするため).
    """
    sleep_fn = sleep if sleep is not None else time.sleep
    attempt = 0
    while True:
        try:
            return func()
        except APIResponseError as e:
            if getattr(e, "status", None) != 429 or attempt >= max_retries:
                raise
            retry_after_header = e.headers.get("Retry-After")
            parsed: float | None = (
                _parse_retry_after(retry_after_header) if retry_after_header is not None else None
            )
            delay: float = parsed if parsed is not None else initial_backoff_sec * (2**attempt)
            sleep_fn(delay)
            attempt += 1
