"""Chunked / map-reduce LLM summarizer for long documents.

設計根拠: ``docs/packages/digestkit/adr/0001-chunked-summarizer-as-separate-class.md``

`LLMSummarizer` は単発呼び出し専用のため、入力がモデルのトークン上限を
超える文書は LLM 側で失敗する。本クラスは「分割 → 部分要約 (map) → 統合 (reduce)」
を再帰的に行い、長文 PDF / 書籍章でも 1 つの最終要約を返す。

短文 (上限内) は単発呼び出しに自動 fallback するため、利用者は短文 / 長文を
事前に判別する必要はない。
"""

from __future__ import annotations

import re
import time
from typing import Any, ClassVar

import litellm
from dotenv import load_dotenv

from ..logging import get_logger
from ..types import Digest, Item
from .llm import LLMSummarizer, SummarizationError

load_dotenv()

log = get_logger(__name__)


# 中立的な map / reduce プロンプト. 利用者が override 可能.
_DEFAULT_MAP_PROMPT = (
    "次のドキュメントの一部を日本語で簡潔に要約してください。"
    "後で複数の部分要約を統合する前提のため、論点・数値・固有名詞は省略しないでください。"
    "\n\n{text}"
)
_DEFAULT_REDUCE_PROMPT = (
    "以下は同一のドキュメントを分割して個別に要約した複数の部分要約です。"
    "重複を排し、矛盾は両論併記し、日本語で簡潔に統合してください。"
    "\n\n{text}"
)

# トークン数の文字数フォールバック係数 (英語近似. 日本語混在でも安全側).
_CHARS_PER_TOKEN_FALLBACK = 4

# 段落分割の正則 (連続改行).
_PARAGRAPH_SPLIT = re.compile(r"\n{2,}")
# 文末の正則 (日本語全角 + ASCII 半角). 全角句読点はあえて含めるため RUF001 を抑制.
_SENTENCE_SPLIT = re.compile(r"(?<=[。．！？!?])\s*")  # noqa: RUF001


class ChunkedLLMSummarizer:
    """長文向けの map-reduce 型要約 Summarizer.

    入力テキストがモデルのトークン上限を超える場合に、内部で

    1. 分割 (token 量基準で段落 → 文 → 文字へフォールバック)
    2. 各チャンクを ``map_prompt`` で部分要約 (map)
    3. 部分要約を結合し、まだ上限超なら ``reduce_prompt`` で再帰 reduce
    4. 最終 reduce 段で ``length`` (``prompts`` キー) に対応するテンプレートで統合

    を行う. 上限内の入力は単発呼び出しに自動 fallback する.

    `length` (`prompts`) との関係:

    * ``prompts`` 未指定: 最終 reduce も ``reduce_prompt`` を使う
      (``LLMSummarizer`` と同じく ``length`` 引数は黙って無視)
    * ``prompts`` 指定: 最終 reduce のみ ``prompts[length or default_length]`` を使う
      (中間 reduce は中立 ``reduce_prompt`` 固定 = 中間段で長さを縛らない方針)

    失敗時:

    * デフォルト fail-fast. ``SummarizationError`` メッセージにチャンク index
      (``chunk i/n``) を含めて提供する.
    """

    #: ``LLMSummarizer.DEFAULT_PROMPTS`` をそのまま再エクスポート (利用者の便宜).
    DEFAULT_PROMPTS: ClassVar[dict[str, str]] = LLMSummarizer.DEFAULT_PROMPTS

    def __init__(
        self,
        provider: str,
        model: str,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int = 0,
        reserve_tokens: int = 8000,
        map_prompt: str = _DEFAULT_MAP_PROMPT,
        reduce_prompt: str = _DEFAULT_REDUCE_PROMPT,
        prompts: dict[str, str] | None = None,
        default_length: str = "standard",
        system_prompt: str = "",
        timeout: float | None = None,
        num_retries: int = 0,
    ) -> None:
        if chunk_size is not None and chunk_size <= 0:
            raise ValueError("chunk_size は正の整数か None")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap は 0 以上")
        if chunk_size is not None and chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap は chunk_size より小さい必要があります")
        if reserve_tokens < 0:
            raise ValueError("reserve_tokens は 0 以上")
        if num_retries < 0:
            raise ValueError("num_retries は 0 以上の整数である必要があります")
        if "{text}" not in map_prompt:
            raise ValueError("map_prompt に '{text}' プレースホルダが必要です")
        if "{text}" not in reduce_prompt:
            raise ValueError("reduce_prompt に '{text}' プレースホルダが必要です")
        if prompts is not None:
            if not prompts:
                raise ValueError("prompts は 1 つ以上のテンプレートを含む必要があります")
            if default_length not in prompts:
                raise ValueError(
                    f"default_length={default_length!r} が prompts のキー "
                    f"{sorted(prompts)} に含まれていません"
                )

        self._provider = provider
        self._model = model
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._reserve_tokens = reserve_tokens
        self._map_prompt = map_prompt
        self._reduce_prompt = reduce_prompt
        self._prompts: dict[str, str] | None = dict(prompts) if prompts else None
        self._default_length = default_length
        self._system_prompt = system_prompt
        self._timeout = timeout
        self._num_retries = num_retries

    # ------------------------------------------------------------------ public

    def summarize(self, text: str, item: Item, *, length: str | None = None) -> Digest:
        full_model = self._full_model()
        threshold = self._effective_chunk_size(full_model)
        final_template = self._final_template(length)

        total_tokens = self._count_tokens(text, full_model)

        # 短文 fallback: 上限内なら最終テンプレートで単発呼び出し
        if total_tokens <= threshold:
            log.info(
                "chunked_single_shot",
                extra={"tokens": total_tokens, "threshold": threshold, "model": full_model},
            )
            return self._complete(final_template, text, item, full_model)

        chunks = self._split_text(text, threshold, full_model)
        log.info(
            "chunked_map_started",
            extra={
                "chunks": len(chunks),
                "tokens": total_tokens,
                "threshold": threshold,
                "model": full_model,
            },
        )

        # ---- map 段
        partial_summaries: list[str] = []
        agg = _MetricsAggregator()
        for i, chunk in enumerate(chunks):
            log.info(
                "chunk_started",
                extra={
                    "index": i,
                    "total": len(chunks),
                    "tokens": self._count_tokens(chunk, full_model),
                },
            )
            try:
                digest = self._complete(self._map_prompt, chunk, item, full_model)
            except SummarizationError as e:
                raise SummarizationError(f"chunk {i}/{len(chunks)}: {e}") from e
            partial_summaries.append(digest.summary)
            agg.add(digest)
            log.info(
                "chunk_completed",
                extra={"index": i, "total": len(chunks), "tokens_out": digest.tokens_out},
            )

        # ---- reduce 段 (再帰)
        # 判定は combined 単体のトークン数で行う (prompt overhead は reserve_tokens で吸収).
        # 中間 reduce 段が縮約に失敗して長さが減らないケースに備え、depth 上限で保険をかける.
        combined = "\n\n".join(partial_summaries)
        depth = 0
        max_depth = 5
        while self._count_tokens(combined, full_model) > threshold:
            if depth >= max_depth:
                raise SummarizationError(
                    f"reduce が {max_depth} 段繰り返しても threshold を下回りませんでした "
                    f"(combined tokens > {threshold}). prompts/モデルを見直してください"
                )
            depth += 1
            sub_chunks = self._split_text(combined, threshold, full_model)
            log.info(
                "chunked_reduce_recursion",
                extra={"depth": depth, "sub_chunks": len(sub_chunks)},
            )
            new_partials: list[str] = []
            for i, chunk in enumerate(sub_chunks):
                try:
                    digest = self._complete(self._reduce_prompt, chunk, item, full_model)
                except SummarizationError as e:
                    raise SummarizationError(
                        f"reduce depth={depth} chunk {i}/{len(sub_chunks)}: {e}"
                    ) from e
                new_partials.append(digest.summary)
                agg.add(digest)
            combined = "\n\n".join(new_partials)

        # ---- 最終 reduce (length 適用)
        final_digest = self._complete(final_template, combined, item, full_model)
        agg.add(final_digest)

        return Digest(
            summary=final_digest.summary,
            tokens_in=agg.tokens_in,
            tokens_out=agg.tokens_out,
            latency_ms=agg.latency_ms,
            model=full_model,
        )

    # ----------------------------------------------------------------- helpers

    def _full_model(self) -> str:
        return f"{self._provider}/{self._model}" if "/" not in self._model else self._model

    def _final_template(self, length: str | None) -> str:
        if self._prompts is None:
            # length 引数は黙って無視 (LLMSummarizer と同じ挙動)
            if length is not None:
                log.debug(
                    "ignoring length=%r because prompts is not configured (using reduce_prompt)",
                    length,
                )
            return self._reduce_prompt
        chosen = length if length is not None else self._default_length
        if chosen not in self._prompts:
            raise ValueError(
                f"length={chosen!r} は prompts のキー {sorted(self._prompts)} に含まれていません"
            )
        return self._prompts[chosen]

    def _effective_chunk_size(self, full_model: str) -> int:
        if self._chunk_size is not None:
            return self._chunk_size
        # max_input_tokens (= 入力 context window) を取得. #23 修正前は
        # litellm.get_max_tokens (= 出力上限) を誤用していたため過剰チャンク化していた.
        context_window = _safe_get_max_tokens(full_model)
        if context_window is None:
            # フォールバック: よくある 8k window を仮定
            log.warning(
                "model_max_tokens_unknown",
                extra={"model": full_model, "fallback": 8000},
            )
            context_window = 8000
        size = context_window - self._reserve_tokens
        if size <= 0:
            raise SummarizationError(
                f"reserve_tokens={self._reserve_tokens} がモデル context window "
                f"{context_window} を超えています"
            )
        return size

    def _count_tokens(self, text: str, full_model: str) -> int:
        try:
            n: int = litellm.token_counter(model=full_model, text=text)  # type: ignore[reportUnknownMemberType]
            return int(n)
        except Exception:
            # 未知モデルや tokenizer 取得失敗時は文字数からの近似
            return max(1, len(text) // _CHARS_PER_TOKEN_FALLBACK)

    def _split_text(self, text: str, threshold: int, full_model: str) -> list[str]:
        """段落 → 文 → 文字 の順でフォールバックしながら threshold 以下に分割."""
        # まず段落に分割し、threshold を超える単一段落は文/文字でさらに分割
        atoms: list[str] = []
        for para in _PARAGRAPH_SPLIT.split(text):
            para = para.strip()
            if not para:
                continue
            if self._count_tokens(para, full_model) <= threshold:
                atoms.append(para)
            else:
                atoms.extend(self._split_paragraph(para, threshold, full_model))

        # オーバーラップは文字数近似で適用
        overlap_chars = self._chunk_overlap * _CHARS_PER_TOKEN_FALLBACK

        chunks: list[str] = []
        current: list[str] = []
        current_text = ""
        for atom in atoms:
            candidate = (current_text + "\n\n" + atom) if current_text else atom
            if self._count_tokens(candidate, full_model) <= threshold:
                current.append(atom)
                current_text = candidate
            else:
                if current_text:
                    chunks.append(current_text)
                # オーバーラップ: 直前 chunk の末尾を新 chunk の先頭に付ける
                if overlap_chars > 0 and current_text:
                    tail = current_text[-overlap_chars:]
                    current = [tail, atom]
                    current_text = tail + "\n\n" + atom
                else:
                    current = [atom]
                    current_text = atom
        if current_text:
            chunks.append(current_text)
        return chunks

    def _split_paragraph(self, para: str, threshold: int, full_model: str) -> list[str]:
        """単一段落が threshold 超のときに文 → 文字にフォールバック."""
        parts: list[str] = []
        for sent in _SENTENCE_SPLIT.split(para):
            sent = sent.strip()
            if not sent:
                continue
            if self._count_tokens(sent, full_model) <= threshold:
                parts.append(sent)
            else:
                # 最後の砦: 文字数で機械分割
                approx_chars = max(1, threshold * _CHARS_PER_TOKEN_FALLBACK)
                for start in range(0, len(sent), approx_chars):
                    parts.append(sent[start : start + approx_chars])
        return parts

    def _complete(self, template: str, text: str, item: Item, full_model: str) -> Digest:
        user_prompt = template.format(text=text, item=item)
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        start = time.perf_counter()
        try:
            response: Any = litellm.completion(  # type: ignore[reportUnknownMemberType]
                model=full_model,
                messages=messages,
                timeout=self._timeout,
                num_retries=self._num_retries,
            )
        except Exception as e:
            raise SummarizationError(str(e)) from e
        latency_ms = int((time.perf_counter() - start) * 1000)

        summary: str = response.choices[0].message.content or ""
        usage: Any = response.usage
        return Digest(
            summary=summary,
            tokens_in=getattr(usage, "prompt_tokens", 0),
            tokens_out=getattr(usage, "completion_tokens", 0),
            latency_ms=latency_ms,
            model=full_model,
        )


# ---------------------------------------------------------------------- module helpers


def _safe_get_max_tokens(full_model: str) -> int | None:
    """モデルの**入力 context window** を返す (チャンクサイズ自動算出用).

    litellm の規約では ``max_tokens`` は出力上限なので、入力 context window として
    扱うべきは ``max_input_tokens``. これを優先し、未公開のバックエンドのみ
    ``max_tokens`` にフォールバックする.

    例 (gemini-2.5-flash):

    * ``max_input_tokens``: 1,048,576  ← これを採用
    * ``max_tokens`` / ``max_output_tokens``: 65,535

    過去 (#23 修正前) は ``litellm.get_max_tokens`` 経由で出力上限の方を読んでいたため、
    1M context window のモデルでも 57k tokens で chunked 経路に突入する不具合があった.
    """
    try:
        raw: Any = litellm.get_model_info(full_model)  # type: ignore[reportUnknownMemberType]
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    info: dict[str, Any] = raw  # type: ignore[reportUnknownVariableType]
    # 入力 context window を優先 (litellm 規約)
    max_input: Any = info.get("max_input_tokens")
    if max_input:
        return int(max_input)
    # 古いバックエンドで max_input_tokens 未公開の場合のみ max_tokens にフォールバック.
    # 注: ここでの max_tokens は厳密には出力上限だが、そもそも max_input_tokens を
    # 公開していないモデルは context window と output limit が同値であることが多い.
    max_tokens: Any = info.get("max_tokens")
    return int(max_tokens) if max_tokens else None


class _MetricsAggregator:
    """map / reduce 全段の token / latency を集計."""

    def __init__(self) -> None:
        self.tokens_in = 0
        self.tokens_out = 0
        self.latency_ms = 0

    def add(self, digest: Digest) -> None:
        self.tokens_in += digest.tokens_in
        self.tokens_out += digest.tokens_out
        self.latency_ms += digest.latency_ms
