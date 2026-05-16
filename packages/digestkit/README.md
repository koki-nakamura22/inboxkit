# digestkit

Personal content digester framework: fetch → extract → LLM summarize → sink

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/ci.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/pypi/pyversions/digestkit?label=python)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Installation

> **Note**: digestkit is not yet published to PyPI. Until the first PyPI release,
> install directly from the umbrella repository's `main` branch using a git URL.

### From git (current)

```bash
pip install "digestkit @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/digestkit"
```

With optional extras:

```bash
pip install "digestkit[pdf,notion] @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/digestkit"
```

For [uv](https://docs.astral.sh/uv/) projects, declare it under `[tool.uv.sources]`:

```toml
[project]
dependencies = ["digestkit"]

[tool.uv.sources]
digestkit = { git = "https://github.com/koki-nakamura22/inboxkit.git", subdirectory = "packages/digestkit", branch = "main" }
```

Pin to a specific commit for reproducibility by replacing `branch = "main"` with `rev = "<sha>"`.

### From PyPI (planned)

Once `digestkit` is published, the standard install path will be:

```bash
pip install digestkit
pip install digestkit[pdf,notion]
```

Tracking issue: [#3](https://github.com/koki-nakamura22/inboxkit/issues/3).

## Quickstart

Create a `.env` file with your LLM API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Define and run your digester:

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

### Programmatic construction (constructor injection)

For dynamic configuration (config files, CLI flags, tests with swapped components),
pass the four core dependencies as constructor kwargs instead of subclassing:

```python
digester = Digester(
    source=LocalDirectorySource("./papers", glob="*.pdf"),
    extractor=PDFExtractor(),
    summarizer=LLMSummarizer(provider="anthropic", model="claude-haiku-4-5"),
    sink=SQLiteSink("digests.db"),
)
digester.run()
```

Both styles are supported and can be mixed: when a subclass defines class attributes,
any kwarg passed to `__init__` overrides them (kwarg wins). This is the same hybrid
pattern used by `seen_store` and `dedup_key`.

### Notion DB → Web fetch → 要約 → Slack 通知

Notion データベースの URL プロパティを起点に Web ページを取得・要約し、Slack に
通知する王道パイプライン. `NotionDatabaseSource(url_property=...)` を指定すると
`item.payload` が URL 文字列になり `WebPageExtractor` とそのまま接続できる
(元の Notion page object は `item.metadata["page"]` から参照可能):

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

`NotionDatabaseSource` は Notion 3.x の Data Sources API (`data_sources/{id}/query`)
に**自動対応**する. 初回 `fetch()` で `databases.retrieve` を 1 回呼び `data_sources`
の有無を判定し、結果はインスタンス内にキャッシュする (2 回目以降の retrieve 呼び出しは
発生しない). 3.x で新規作成された DB は新 API、旧 DB は旧 `databases/{id}/query` へ
透過的に fallback されるため、利用者側で API バージョンを意識する必要はない.

## Long documents (chunked / map-reduce)

For documents that exceed a model's context window (long PDFs, book chapters), use
`ChunkedLLMSummarizer`. It splits the input, summarizes each chunk (map), and
recursively merges the partial summaries (reduce). Inputs that fit in the window
fall back to a single LLM call automatically.

```python
from digestkit.summarizers import ChunkedLLMSummarizer

summarizer = ChunkedLLMSummarizer(
    provider="anthropic",
    model="claude-haiku-4-5",
    chunk_size=80_000,    # tokens per chunk; defaults to model max - reserve_tokens
    chunk_overlap=0,
    prompts=ChunkedLLMSummarizer.DEFAULT_PROMPTS,  # opt-in length control
    default_length="standard",
)
```

`length` (`"short"` / `"standard"` / `"detailed"`) is applied **only at the final
reduce step**; intermediate stages use a neutral merge prompt to avoid
over-compressing mid-pipeline. On a per-chunk LLM failure the call fails fast with
the chunk index in the error message.

## Anthropic prompt caching (cache_control)

`LLMSummarizer` の `system_prompt` は `str` のほか、LiteLLM が受け付ける
content block のリスト (`list[dict]`) でも指定できる。これにより Anthropic
の prompt caching (`cache_control: {"type": "ephemeral"}`) を有効にして、
長い system prompt の入力トークン課金を大幅に削減できる:

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

`system_prompt` を従来通り `str` で渡した場合の挙動は変わらない (後方互換)。
詳細は LiteLLM 公式ドキュメントを参照:
<https://docs.litellm.ai/docs/providers/anthropic#prompt-caching>

## Configuration

Set your LLM provider API key in a `.env` file (loaded automatically via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...  # Anthropic Claude
OPENAI_API_KEY=sk-...         # OpenAI GPT
GOOGLE_API_KEY=...            # Google Gemini
```

## CLI

```bash
digestkit run my_digester.py
```

## Architecture

digestkit implements a **1:1 pipeline**: for each item fetched from the source, it extracts
text, sends it to an LLM for summarization, and writes the result to the configured sink.
Items that fail at any stage are collected in `RunResult.failures`; the pipeline continues
rather than aborting on first error.

digestkit is the Phase 1 component of the
[inboxkit](https://github.com/koki-nakamura22/inboxkit) umbrella monorepo, which will also
host future packages for RAG ingestion and personal knowledge bases.

## Optional Dependencies

| Extra    | Packages           | Use case                       |
|----------|--------------------|--------------------------------|
| `pdf`    | pypdf              | Extract text from PDF files    |
| `web`    | trafilatura, httpx | Fetch and extract web articles |
| `notion` | notion-client      | Fetch pages from Notion        |
| `slack`  | httpx              | Fetch messages from Slack      |
| `email`  | —                  | Fetch emails (IMAP/SMTP)       |
| `all`    | all of the above   | Install everything             |

Install any extra with `pip install digestkit[<extra>]`.
