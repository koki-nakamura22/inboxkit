**English** | [日本語](README.ja.md)

# digestkit-core

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/digestkit-core-inspection.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/digestkit-core-inspection.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/pypi/pyversions/digestkit-core?label=python)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Neutral core library providing `Source` / `Extractor` protocols and reusable
concrete implementations shared by [digestkit](../digestkit) (human-facing
1:1 digest pipeline) and [rag-ingest](../rag-ingest) (machine-facing 1:N
ingestion pipeline).

`digestkit-core` is deliberately kept free of LLM, vector-store, and
notification dependencies so it stays usable across both consumers.

## What's inside

| Module                                       | Provides                                                  |
| -------------------------------------------- | --------------------------------------------------------- |
| `digestkit_core.protocols`                   | `Source`, `Extractor` (`runtime_checkable` Protocols)     |
| `digestkit_core.types`                       | `Item`, `Digest`, `DigestkitError`, `FailureInfo`, ...    |
| `digestkit_core.sources.local_directory`     | `LocalDirectorySource` (filesystem glob)                  |
| `digestkit_core.sources.notion_database`     | `NotionDatabaseSource` (Notion DB query + ack callbacks)  |
| `digestkit_core.extractors.pdf`              | `PDFExtractor` + `ExtractionError`                        |
| `digestkit_core.extractors.webpage`          | `WebPageExtractor` (httpx + trafilatura)                  |

## Installation

> **Note**: digestkit-core is not yet published to PyPI. Install from the
> umbrella repository's `main` branch using a git URL until the first release.

```bash
pip install "digestkit-core @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/digestkit-core"
```

For [uv](https://docs.astral.sh/uv/) projects:

```toml
[project]
dependencies = ["digestkit-core>=0.1,<0.2"]

[tool.uv.sources]
digestkit-core = { git = "https://github.com/koki-nakamura22/inboxkit.git", subdirectory = "packages/digestkit-core", branch = "main" }
```

End users will typically not depend on `digestkit-core` directly. Installing
`digestkit` or `rag-ingest` pulls it in automatically.

## Neutrality contract

`digestkit-core` is forbidden to depend on:

- LLM clients (`litellm`, provider SDKs)
- Vector stores (`sqlite-vec`, ...)
- Notification systems (SMTP, Slack SDK)
- `digestkit` or `rag-ingest` themselves (reverse-direction dependency)

This is enforced in CI via `.github/workflows/digestkit-core-inspection.yml`.
The rationale is documented in
[ADR-0003](../../docs/adr/0003-digestkit-core-extraction-policy.md).

## Contributing

See the umbrella [CONTRIBUTING.md](../../CONTRIBUTING.md) for development
setup, lint / format / typecheck targets, and the pre-commit hook.
