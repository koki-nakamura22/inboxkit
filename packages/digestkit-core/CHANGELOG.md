# Changelog — digestkit-core

All notable changes to `digestkit-core` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **`PDFExtractor` now uses pypdfium2 (PDFium) by default instead of pypdf**
  ([#55](https://github.com/koki-nakamura22/inboxkit/issues/55)). pypdf cannot map
  CID fonts embedded with `/Encoding /Identity-H` + Adobe-Japan1 ordering when the
  font carries no `ToUnicode` CMap, which is common in commercially published
  Japanese PDFs. It returns mojibake **without raising**, so the pipeline reports
  success and the summarizer is fed unreadable text.
- **The `pdf` extra now installs `pypdfium2` instead of `pypdf`.** Environments that
  install `digestkit-core[pdf]` pick up the new engine automatically; those pinning
  `pypdf` directly must switch to the new `pdf-pypdf` extra.

### Added

- `PDFExtractor(engine=...)` — `"pypdfium2"` (default) or `"pypdf"`. An unknown
  engine name raises `ValueError` at construction time.
- `PDFExtractor.engine` property exposing the resolved engine.
- `digestkit_core.extractors.pdf.PDFEngine` / `DEFAULT_ENGINE` for callers that want
  to reference the engine names symbolically.
- New `pdf-pypdf` extra (`pypdf>=4`) for opting back into the previous engine.
- Missing-engine imports now raise `ExtractionError` naming the extra to install,
  instead of a bare `ImportError`.

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
