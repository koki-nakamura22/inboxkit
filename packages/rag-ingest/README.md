**English** | [日本語](README.ja.md)

# rag-ingest

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/rag-ingest-ci.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/rag-ingest-ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/pypi/pyversions/rag-ingest?label=python)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Machine-facing 1:N ingestion pipeline:
**fetch → extract → chunk → embed → vector sink.**

`rag-ingest` is the Phase 2 component of the
[inboxkit](https://github.com/koki-nakamura22/inboxkit) umbrella monorepo.
It reuses the `Source` / `Extractor` abstractions from
[digestkit-core](../digestkit-core) and adds chunking, embedding, and a
vector-store sink layer suitable for feeding a personal RAG corpus.

## Pipeline shape

```
Source.fetch() ─► Item
                  │
                  ▼
            Extractor.extract() ─► str
                                   │
                                   ▼
                            Chunker.chunk() ─► list[Chunk]   (1 → N)
                                                 │
                                                 ▼
                                       Embedder.embed() ─► list[Vector]
                                                            │
                                                            ▼
                                                  VectorSink.write()
                                                  (1 Source item = 1 transaction)
```

- **1 Source item = 1 transaction**: partial-failure boundary is per item
- Per-item failures are collected; the pipeline continues rather than aborting
- `IngestContext` propagates `embedder_provider` / `embedder_model` /
  `chunker_config` / `extractor_version` / `extracted_at` to the sink so that
  downstream tooling can reason about provenance

## Installation

> **Note**: rag-ingest is not yet published to PyPI. Install from the
> umbrella repository's `main` branch using a git URL until the first release.

```bash
pip install "rag-ingest @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/rag-ingest"
```

For [uv](https://docs.astral.sh/uv/) projects:

```toml
[project]
dependencies = ["rag-ingest"]

[tool.uv.sources]
rag-ingest = { git = "https://github.com/koki-nakamura22/inboxkit.git", subdirectory = "packages/rag-ingest", branch = "main" }
```

`digestkit-core` is pulled in automatically as a transitive dependency.

## Quickstart

Set an embedding provider key in `.env`:

```
OPENAI_API_KEY=sk-...
```

Define and run an ingester:

```python
from digestkit_core.sources import LocalDirectorySource
from digestkit_core.extractors import PDFExtractor
from rag_ingest import Ingester
from rag_ingest.chunkers import FixedSizeChunker
from rag_ingest.embedders import LLMEmbedder
from rag_ingest.sinks import SQLiteVecSink

class PaperIngester(Ingester):
    source = LocalDirectorySource("./papers", glob="*.pdf")
    extractor = PDFExtractor()
    chunker = FixedSizeChunker(unit="token", size=512, overlap=64)
    embedder = LLMEmbedder(provider="openai", model="text-embedding-3-small")
    sink = SQLiteVecSink(db_path="rag.db", dim=1536)

if __name__ == "__main__":
    PaperIngester().run()
```

`Ingester(...)` can also be instantiated directly with kwargs for
configuration-driven or test setups, just like `digestkit.Digester`.

## CLI

```bash
rag-ingest run my_ingester.py
```

Flags:

- `--dry-run` — runs `extract` and `chunk` only; skips embedding and sink writes
- `--limit N` — process at most N source items

## Components

| Module                                | Class / Function          | Notes                                                      |
| ------------------------------------- | ------------------------- | ---------------------------------------------------------- |
| `rag_ingest.ingester`                 | `Ingester` / `RunResult`  | Pipeline driver, dry-run support, per-item failure capture |
| `rag_ingest.chunkers.fixed_size`      | `FixedSizeChunker`        | Fixed-length chunks (token or char unit) with overlap      |
| `rag_ingest.embedders.llm`            | `LLMEmbedder`             | LiteLLM-backed embedder; batched calls                     |
| `rag_ingest.sinks.sqlite_vec`         | `SQLiteVecSink`           | sqlite-vec writer; per-source 1 transaction                |
| `rag_ingest.protocols`                | `Chunker` / `Embedder` / `VectorSink` | `runtime_checkable` Protocols                  |

## Relationship to digestkit

Both packages share `Source` / `Extractor` abstractions via
[digestkit-core](../digestkit-core). digestkit produces **summaries for
humans** (1:1); rag-ingest produces **chunks + embeddings for retrieval by
machines** (1:N). They are deliberately kept independent: do **not** feed
digestkit's compressed summaries into rag-ingest — that would discard the
information needed for retrieval quality. Run both from the same Source if
you want both outputs.

## Optional dependencies

The base install pulls in everything required to run the full pipeline
(`litellm`, `tiktoken`, `sqlite-vec`, `python-dotenv`, `click`). `digestkit-core`
brings the source/extractor SDKs (`pypdf`, `trafilatura`, `notion-client`).

## Contributing

See the umbrella [CONTRIBUTING.md](../../CONTRIBUTING.md) for development
setup, lint / format / typecheck targets, and the pre-commit hook.
