**English** | [日本語](README.ja.md)

# inboxkit

> Umbrella monorepo for personal "inbox" ingestion tooling — fetch content from the places where your reading / writing / signals already accumulate (Notion, web, PDF, Slack, email, ...), then digest, ingest into RAG, and eventually serve it back to AI coding agents.

## Philosophy

The information that actually shapes your thinking is already sitting in your inboxes — saved Notion pages, half-read PDFs, web articles bookmarked at 1am, Slack threads, mail. It rarely makes it back into a place where you (or an AI agent acting on your behalf) can ask questions of it later. `inboxkit` is a set of cooperating Python packages that treat those inboxes as first-class data sources and turn them into reusable artifacts: human-readable digests, RAG corpora, and (eventually) a personal knowledge base queryable via MCP.

Each package is independently installable and useful on its own; the umbrella exists so the shared abstractions (`Source` / `Extractor` / cache / sink) can be extracted only after they have been validated by more than one real call site (rule of three).

## Packages

| Package | Role | Phase | Status |
|---|---|---|---|
| [digestkit](./packages/digestkit) | 1:1 pipeline: fetch → extract → LLM summarize → sink | Phase 1 | In progress (pre-PyPI) |
| digestkit-core | Shared `Source` / `Extractor` abstractions, extracted once a second consumer (`rag-ingest`) needs them | Phase 2 | Not started |
| rag-ingest | 1:N pipeline: fetch → extract → chunk → embed → vector store | Phase 2 | Not started |
| personal-rag | SQLite + sqlite-vec store + MCP server so AI coding agents can query the personal corpus | Phase 3 | Not started |

Naming note: the umbrella repo is `inboxkit` but the Phase 1 PyPI package is `digestkit`. Background and rationale live in [packages/digestkit/README.md](./packages/digestkit/README.md) and the project PRD.

## Repository layout

```
inboxkit/
├── README.md                       ← this file (umbrella overview, English)
├── README.ja.md                    ← Japanese version
├── CONTRIBUTING.md                 ← contributor / development setup (English)
├── CONTRIBUTING.ja.md              ← Japanese version
├── Makefile                        ← unified lint / format / typecheck / test targets
├── pyproject.toml                  ← uv workspace root
├── packages/
│   └── digestkit/                  ← Phase 1 package (independently installable)
│       ├── README.md
│       ├── pyproject.toml
│       ├── src/digestkit/
│       └── tests/
└── docs/                           ← umbrella-level docs (gitignored flow info + selected stock docs)
```

Phase 2 / 3 packages will sit at the same level under `packages/` when they land.

## Shared core extraction policy

We deliberately do **not** extract a shared `digestkit-core` up-front. The current single app (`digestkit`) should not pay an abstraction tax for siblings that do not yet exist.

The plan progresses through three phases:

1. **Phase 1 (current)** — `digestkit` only. No core.
2. **Phase 2** — `rag-ingest` is added alongside `digestkit`. The two apps will intentionally duplicate their shared parts (`Source` / `Extractor`) so the genuinely-common surface can be observed from two real call sites before being extracted into `digestkit-core` (rule of three).
3. **Phase 3** — `personal-rag` consumes the corpus produced by `rag-ingest` and exposes it to AI coding agents via MCP.

Likely shared surface (watchlist for Phase 2):

- `Source` / `Extractor` protocols and their common implementations (Notion DB, web, PDF, local directory)
- `SeenStore` / dedup-key abstraction
- dotenv + redacted logging boilerplate
- CLI plumbing (entrypoint, config loading)

Likely never-shared (will stay per-package):

- `Summarizer` (digestkit only — 1:1 LLM call)
- `Embedder` / `Chunker` / vector-store sink (rag-ingest only — 1:N flow)
- MCP server surface (personal-rag only)

## Privacy / Security

These tools send personal content to third-party LLM and embedding providers for summarization / vectorization.

Common rules every package in this family must enforce:

- **API keys are read from environment variables only** (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) via `python-dotenv`. They are redacted from all log output before emission.
- **Source-side credentials (Notion / Slack tokens) are loaded from env as well.** Never hardcoded, never written to the cache or output.
- **PII handling is the user's responsibility at the source boundary.** `inboxkit` does not attempt to mask emails, names, or message authors inside fetched content — if you cannot share the content with a third-party LLM, do not pipe it through `inboxkit`.
- **`docs/` and `tasks.json` are gitignored** as flow information (see CONTRIBUTING for the rationale). Stock documents are promoted to canonical locations explicitly.

Package-specific privacy details live in each package's README.

## Install / Usage

Each package installs and runs independently. See the per-package README for installation, configuration, and examples:

- [digestkit — README](./packages/digestkit/README.md)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup (uv workspace, pre-commit hooks, Makefile targets).

## License

Apache License 2.0 — see [LICENSE](LICENSE).
