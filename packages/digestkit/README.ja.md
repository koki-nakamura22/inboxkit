[English](README.md) | **日本語**

# digestkit

個人コンテンツ digester フレームワーク: fetch → extract → LLM 要約 → sink

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/ci.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/pypi/pyversions/digestkit?label=python)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## インストール

> **Note**: digestkit はまだ PyPI に publish されていません。初回リリースまでは umbrella リポジトリの `main` ブランチから git URL 経由で install してください。

### git から (現状)

```bash
pip install "digestkit @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/digestkit"
```

extras 付きの場合:

```bash
pip install "digestkit[pdf,notion] @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/digestkit"
```

[uv](https://docs.astral.sh/uv/) プロジェクトでは `[tool.uv.sources]` で宣言:

```toml
[project]
dependencies = ["digestkit"]

[tool.uv.sources]
digestkit = { git = "https://github.com/koki-nakamura22/inboxkit.git", subdirectory = "packages/digestkit", branch = "main" }
```

再現性のために特定 commit に pin したい場合は `branch = "main"` を `rev = "<sha>"` に置き換えてください。

### PyPI から (予定)

`digestkit` が publish された後の標準的な install 方法:

```bash
pip install digestkit
pip install digestkit[pdf,notion]
```

トラッキング Issue: [#3](https://github.com/koki-nakamura22/inboxkit/issues/3)

## Quickstart

`.env` に LLM API key を書きます:

```
ANTHROPIC_API_KEY=sk-ant-...
```

digester を定義して実行:

```python
from digestkit import Digester
from digestkit.sources import LocalDirectorySource
from digestkit.extractors import PDFExtractor
from digestkit.summarizers import LLMSummarizer
from digestkit.sinks import SQLiteSink

class PdfDigester(Digester):
    source = LocalDirectorySource("./papers", glob="*.pdf")
    extractor = PDFExtractor()
    summarizer = LLMSummarizer(provider="anthropic", model="claude-haiku-4-5")
    sink = SQLiteSink("digests.db")

if __name__ == "__main__":
    PdfDigester().run()
```

### プログラマティック構築 (コンストラクタインジェクション)

設定ファイル / CLI フラグ / コンポーネントを差し替えたテスト等、動的な設定が必要な場合はサブクラス化せず、4 つのコア依存をコンストラクタ kwarg で渡せます:

```python
digester = Digester(
    source=LocalDirectorySource("./papers", glob="*.pdf"),
    extractor=PDFExtractor(),
    summarizer=LLMSummarizer(provider="anthropic", model="claude-haiku-4-5"),
    sink=SQLiteSink("digests.db"),
)
digester.run()
```

どちらのスタイルも両立可。サブクラスがクラス属性を定義していても `__init__` に渡した kwarg が**勝ち**ます。`seen_store` / `dedup_key` でも同じハイブリッドパターンを採用しています。

### Notion DB → Web fetch → 要約 → Slack 通知

Notion データベースの URL プロパティを起点に Web ページを取得・要約し、Slack に通知する王道パイプライン。`NotionDatabaseSource(url_property=...)` を指定すると `item.payload` が URL 文字列になり `WebPageExtractor` とそのまま接続できます (元の Notion page object は `item.metadata["page"]` から参照可能):

```python
from digestkit import Digester
from digestkit.sources.notion_database import NotionDatabaseSource
from digestkit.extractors.webpage import WebPageExtractor
from digestkit.summarizers import LLMSummarizer
from digestkit.sinks.slack import SlackSink

digester = Digester(
    source=NotionDatabaseSource(
        database_id="<your-db-id>",
        url_property="URL",                 # ← payload を URL 文字列にするモード
        status_property="Status",
        status_value_success="処理済み",
        query_filter={"property": "Status", "select": {"equals": "未読"}},
    ),
    extractor=WebPageExtractor(),
    summarizer=LLMSummarizer(provider="anthropic", model="claude-haiku-4-5"),
    sink=SlackSink(webhook_url="https://hooks.slack.com/..."),
)
digester.run()
```

`NotionDatabaseSource` は Notion 3.x の Data Sources API (`data_sources/{id}/query`) に**自動対応**します。初回 `fetch()` で `databases.retrieve` を 1 回呼び `data_sources` の有無を判定し、結果はインスタンス内にキャッシュします (2 回目以降の retrieve 呼び出しは発生しません)。3.x で新規作成された DB は新 API、旧 DB は旧 `databases/{id}/query` へ透過的に fallback されるため、利用者側で API バージョンを意識する必要はありません。

## 長文ドキュメント (chunked / map-reduce)

モデルのコンテキストウィンドウを超える入力 (長い PDF、書籍チャプター等) には `ChunkedLLMSummarizer` を使います。入力を分割し、各 chunk を要約 (map)、部分要約を再帰的にマージ (reduce) します。ウィンドウに収まる入力は単一 LLM コールへ自動 fallback します。

```python
from digestkit.summarizers import ChunkedLLMSummarizer

summarizer = ChunkedLLMSummarizer(
    provider="anthropic",
    model="claude-haiku-4-5",
    chunk_size=80_000,    # chunk 当たり tokens。デフォルトは model max - reserve_tokens
    chunk_overlap=0,
    prompts=ChunkedLLMSummarizer.DEFAULT_PROMPTS,  # opt-in の長さ制御
    default_length="standard",
)
```

`length` (`"short"` / `"standard"` / `"detailed"`) は**最終 reduce ステップのみ**で適用されます。中間段では neutral な merge prompt を使い、パイプライン途中での過剰圧縮を避けます。chunk 単位の LLM 失敗では chunk index 付きエラーで fail-fast します。

## Anthropic prompt caching (cache_control)

`LLMSummarizer.system_prompt` は `str` のほか、LiteLLM が受け付ける content block のリスト (`list[dict]`) でも指定できます。これにより Anthropic の prompt caching (`cache_control: {"type": "ephemeral"}`) を有効にして、長い system prompt の入力トークン課金を大幅に削減できます:

```python
from digestkit.summarizers import LLMSummarizer

summarizer = LLMSummarizer(
    provider="anthropic",
    model="claude-sonnet-4-6",
    system_prompt=[
        {
            "type": "text",
            "text": "<長い system prompt (JSON スキーマ・出力例など)>",
            "cache_control": {"type": "ephemeral"},
        },
    ],
)
```

`system_prompt` を従来通り `str` で渡した場合の挙動は変わりません (後方互換)。

block 構造を意識せず system prompt 全体をキャッシュしたいだけの場合は、`system_prompt_cache=True` フラグを指定する簡素な経路も用意しています:

```python
summarizer = LLMSummarizer(
    provider="anthropic",
    model="claude-sonnet-4-6",
    system_prompt="<長い system prompt>",
    system_prompt_cache=True,   # str を ephemeral cache_control 付き block に自動変換
)
```

複数 block のうち一部だけキャッシュしたい等の細かい制御が必要な場合は list 指定 (上記サンプル) を使います。`system_prompt_cache=True` と list 指定は同時に使えません (cache_control の制御権が衝突するため)。

詳細は LiteLLM 公式ドキュメントを参照:
<https://docs.litellm.ai/docs/providers/anthropic#prompt-caching>

## 設定

`.env` ファイルに LLM プロバイダの API key を設定します (`python-dotenv` で自動 load):

```
ANTHROPIC_API_KEY=sk-ant-...  # Anthropic Claude
OPENAI_API_KEY=sk-...         # OpenAI GPT
GOOGLE_API_KEY=...            # Google Gemini
```

## CLI

```bash
digestkit run my_digester.py
```

## アーキテクチャ

digestkit は **1:1 パイプライン**を実装します: Source から fetch した各 item に対してテキスト抽出 → LLM 要約 → 設定された sink へ書き込み。途中で失敗した item は `RunResult.failures` に集約され、最初のエラーで全体を中断する代わりにパイプラインは継続します。

digestkit は [inboxkit](https://github.com/koki-nakamura22/inboxkit) umbrella monorepo の Phase 1 コンポーネントです。同 umbrella は今後 RAG 取り込み / 個人ナレッジベース用の追加パッケージもホストします。

## オプション依存 (extras)

| Extra    | パッケージ         | 用途                                  |
| -------- | ------------------ | ------------------------------------- |
| `pdf`    | pypdf              | PDF ファイルからのテキスト抽出        |
| `web`    | trafilatura, httpx | Web 記事の取得 + 抽出                 |
| `notion` | notion-client      | Notion からのページ取得               |
| `slack`  | httpx              | Slack からのメッセージ取得            |
| `email`  | —                  | メール (IMAP/SMTP) からの取得         |
| `all`    | 上記すべて         | すべて install                        |

`pip install digestkit[<extra>]` で任意の extra を install できます。

## コントリビュート

開発セットアップ / lint・format・typecheck ターゲット / pre-commit フックについては umbrella の [CONTRIBUTING.md](../../CONTRIBUTING.md) を参照してください。
