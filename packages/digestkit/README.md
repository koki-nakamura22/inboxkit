**English** | [日本語](README.ja.md)

# digestkit

Personal content digester framework: fetch → extract → LLM summarize → sink

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/ci.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](https://opensource.org/licenses/Apache-2.0)
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

### Notion DB → web fetch → summarize → Slack

A common pipeline: walk a Notion database's URL property, fetch + summarize
each page, post to Slack. Specifying `NotionDatabaseSource(url_property=...)`
makes `item.payload` a URL string so `WebPageExtractor` connects directly
(the original Notion page object remains available at `item.metadata["page"]`):

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

`NotionDatabaseSource` **transparently handles** Notion 3.x's Data Sources API
(`data_sources/{id}/query`). The first `fetch()` makes a single
`databases.retrieve` call to detect whether `data_sources` are present and
caches the result on the instance (no further retrieve calls after that).
DBs created on 3.x use the new API; legacy DBs fall back to the older
`databases/{id}/query` automatically — callers don't need to think about
API versions.

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

`LLMSummarizer.system_prompt` accepts either a `str` or a list of LiteLLM
content blocks (`list[dict]`). The list form lets you enable Anthropic
prompt caching (`cache_control: {"type": "ephemeral"}`) so that the input
tokens of a long system prompt are billed at the cache-hit rate:

```python
from digestkit.summarizers import LLMSummarizer

summarizer = LLMSummarizer(
    provider="anthropic",
    model="claude-sonnet-4-6",
    system_prompt=[
        {
            "type": "text",
            "text": "<long system prompt (JSON schema, output examples, ...)>",
            "cache_control": {"type": "ephemeral"},
        },
    ],
)
```

Passing `system_prompt` as a plain `str` keeps the previous behavior
(backward compatible).

If you just want to cache the entire system prompt without dealing with
content blocks yourself, use the `system_prompt_cache=True` shortcut:

```python
summarizer = LLMSummarizer(
    provider="anthropic",
    model="claude-sonnet-4-6",
    system_prompt="<long system prompt>",
    system_prompt_cache=True,   # auto-wraps the str in an ephemeral cache_control block
)
```

For finer control (caching only some of several blocks, etc.), use the list
form shown above. `system_prompt_cache=True` and the list form are mutually
exclusive (they fight over control of `cache_control`).

See the LiteLLM docs for details:
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

## Contributing

See the umbrella [CONTRIBUTING.md](../../CONTRIBUTING.md) for development
setup, lint / format / typecheck targets, and the pre-commit hook.
