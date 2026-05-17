# digestkit-core

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/digestkit-core-inspection.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/digestkit-core-inspection.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/pypi/pyversions/digestkit-core?label=python)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Core Source / Extractor protocols and concrete implementations for the digestkit ecosystem.

Provides `Source`, `Extractor`, `Item`, and concrete implementations like
`LocalDirectorySource`, `NotionDatabaseSource`, `PDFExtractor`, `WebPageExtractor`
as a neutral library without LLM or vector-store dependencies.
