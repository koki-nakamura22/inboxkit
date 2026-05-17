# Changelog — digestkit

All notable changes to `digestkit` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-17

Initial PyPI release of `digestkit`, the Phase 1 component of the
[inboxkit](https://github.com/koki-nakamura22/inboxkit) umbrella project.

Provides a 1:1 personal content digester framework:
**fetch → extract → LLM summarize → sink.** New digesters (PDF / Notion /
RSS / Pocket / ...) can typically be written in under 30 lines by composing
the four protocol-driven layers.

### Added (pipeline / API)

- `digestkit.Digester` — pipeline driver, subclass- or kwarg-injected, with
  per-item failure capture in `RunResult.failures`
- `digestkit.protocols`:
  - `Source` / `Extractor` / `Summarizer` / `Sink` (`runtime_checkable`)
  - `AckSource` — per-item ack callback variant for write-back sources
- `digestkit.sources`:
  - `LocalDirectorySource` (filesystem glob)
  - `NotionDatabaseSource` with Notion 3.x Data Sources API auto-detection
    and AckSource conformance (`notion` extra)
- `digestkit.extractors`:
  - `PDFExtractor` (`pdf` extra: `pypdf`)
  - `WebPageExtractor` (`web` extra: `trafilatura` + `httpx`)
- `digestkit.summarizers`:
  - `LLMSummarizer` — thin LiteLLM wrapper (ADR-0002)
  - `ChunkedLLMSummarizer` — map / reduce for long documents with
    final-stage length control (`short` / `standard` / `detailed`)
  - Anthropic prompt caching support via either `system_prompt` content
    blocks or the `system_prompt_cache=True` shortcut
- `digestkit.sinks`:
  - `SQLiteSink` / `NotionPageSink` / `SlackSink` / `EmailSink` / `CompositeSink`
- `digestkit.dedup.SQLiteSeenStore` + `content_sha256_key` helper
- CLI: `digestkit run <module>` entry point

### Added (Phase 2c re-export layer)

- `digestkit-core` is now a base dependency (`digestkit-core>=0.1,<0.2`)
- `digestkit.protocols.{Source, Extractor}`, `digestkit.types.{Item, Digest,
  FailureInfo, DigestkitError, ConfigurationError}`,
  `digestkit.sources.{local_directory, notion_database}`,
  `digestkit.extractors.{pdf, webpage}`, and `digestkit.digester.FailureInfo`
  are now **canonical in `digestkit_core`** and **re-exported** from
  `digestkit` for backward compatibility
- `packages/digestkit/tests/test_public_api_compat.py` machine-verifies
  that every Phase 1 import path still resolves and that `is` identity is
  preserved between `digestkit.X` and `digestkit_core.X`
- Rationale: [ADR-0003](../../docs/adr/0003-digestkit-core-extraction-policy.md)
- Phase 2c was validated end-to-end against the existing `pdfsum` and
  `read-later-digest` consumers (529 downstream tests + a real PDF
  summarization e2e), with zero source-code changes required on those
  callers' side

### Compatibility

- Python 3.11 / 3.12 / 3.13 supported
- License: Apache-2.0 (full text included in the wheel via PEP 639)
- Extras: `pdf` / `web` / `notion` / `slack` / `email` / `all`

### Related ADRs

- [ADR-0001](../../docs/adr/0001-monorepo-naming-divergence.md) — why the
  umbrella repo is named `inboxkit` while the Phase 1 PyPI package is
  `digestkit`
- [ADR-0002](../../docs/adr/0002-llm-abstraction-via-litellm.md) — LiteLLM
  one-dependency policy for LLM provider abstraction
- [ADR-0003](../../docs/adr/0003-digestkit-core-extraction-policy.md) —
  digestkit-core extraction scope and public-API immutability policy
- [ADR-0004](../../docs/adr/0004-monorepo-publish-strategy.md) — monorepo
  publish strategy (tag prefix, independent versions, staged rollout)

[Unreleased]: https://github.com/koki-nakamura22/inboxkit/compare/digestkit-v0.1.0...HEAD
[0.1.0]: https://github.com/koki-nakamura22/inboxkit/releases/tag/digestkit-v0.1.0
