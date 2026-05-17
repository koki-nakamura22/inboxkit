# Changelog — digestkit-core

All notable changes to `digestkit-core` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-17

Initial release. Extracted from `digestkit` during Phase 2c of the
[inboxkit](https://github.com/koki-nakamura22/inboxkit) umbrella project so
that both `digestkit` (1:1 digest pipeline) and `rag-ingest` (1:N ingestion
pipeline) can share the same `Source` / `Extractor` abstractions and concrete
implementations without forcing either consumer to depend on the other.

The extraction policy and rationale are documented in
[ADR-0003](../../docs/adr/0003-digestkit-core-extraction-policy.md).

### Added

- `digestkit_core.protocols.Source` / `digestkit_core.protocols.Extractor`
  — `runtime_checkable` Protocol pair for the fetch / extract pair
- `digestkit_core.types` — shared DTOs:
  - `Item` (frozen dataclass: `id` / `payload` / `metadata`)
  - `Digest` (frozen dataclass: summary + token / latency / model fields)
  - `FailureInfo` / `FailureStage` (per-item failure record for ack callbacks)
  - `DigestkitError` (ecosystem-wide exception base)
  - `ConfigurationError(DigestkitError)`
- `digestkit_core.sources.local_directory.LocalDirectorySource`
  — filesystem glob source (no extra dependencies)
- `digestkit_core.sources.notion_database.NotionDatabaseSource`
  — Notion DB query source with ack callbacks (`notion` extra: `notion-client`)
  - Transparent fallback between the Notion 3.x Data Sources API
    (`data_sources/{id}/query`) and the legacy `databases/{id}/query`
- `digestkit_core.extractors.pdf.PDFExtractor` + `ExtractionError`
  (`pdf` extra: `pypdf`)
- `digestkit_core.extractors.webpage.WebPageExtractor`
  (`web` extra: `trafilatura` + `httpx`)
- `digestkit_core._notion_retry` — private helper for 429 retry shared
  between Notion-related modules (not part of the public API)
- Apache-2.0 license file included in the wheel via PEP 639
  (`license-files = ["LICENSE"]` in `pyproject.toml`)

### Neutrality contract

`digestkit-core` is forbidden to depend on LLM clients (`litellm`,
provider SDKs), vector stores (`sqlite-vec`, ...), notification systems
(SMTP / Slack SDK), or the higher-level packages (`digestkit` /
`rag-ingest`). This is enforced by
[`.github/workflows/digestkit-core-inspection.yml`](../../.github/workflows/digestkit-core-inspection.yml).

### Compatibility

- Python 3.11 / 3.12 / 3.13 supported
- All public symbols are also re-exported from `digestkit` so existing
  Phase 1 code (`from digestkit.protocols import Source`, etc.) continues
  to work unchanged
- `is` identity is preserved between `digestkit_core.X` and `digestkit.X`
  (verified by `packages/digestkit/tests/test_public_api_compat.py`)

[Unreleased]: https://github.com/koki-nakamura22/inboxkit/compare/digestkit-core-v0.1.0...HEAD
[0.1.0]: https://github.com/koki-nakamura22/inboxkit/releases/tag/digestkit-core-v0.1.0
