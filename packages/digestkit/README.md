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
