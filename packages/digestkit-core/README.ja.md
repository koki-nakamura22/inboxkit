[English](README.md) | **日本語**

# digestkit-core

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/digestkit-core-inspection.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/digestkit-core-inspection.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/pypi/pyversions/digestkit-core?label=python)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[digestkit](../digestkit) (人間向け 1:1 digest パイプライン) と [rag-ingest](../rag-ingest) (機械向け 1:N 取り込みパイプライン) の双方が共有する `Source` / `Extractor` プロトコルと汎用具象実装を提供する**中立コアライブラリ**。

`digestkit-core` は両者で利用可能であり続けるため、LLM / ベクトルストア / 通知系には**意図的に依存しない**設計です。

## 提供する内容

| モジュール                                   | 提供するもの                                              |
| -------------------------------------------- | --------------------------------------------------------- |
| `digestkit_core.protocols`                   | `Source` / `Extractor` (`runtime_checkable` Protocol)     |
| `digestkit_core.types`                       | `Item` / `Digest` / `DigestkitError` / `FailureInfo` ほか |
| `digestkit_core.sources.local_directory`     | `LocalDirectorySource` (ファイルシステム glob)            |
| `digestkit_core.sources.notion_database`     | `NotionDatabaseSource` (Notion DB query + ack callback)   |
| `digestkit_core.extractors.pdf`              | `PDFExtractor` + `ExtractionError`                        |
| `digestkit_core.extractors.webpage`          | `WebPageExtractor` (httpx + trafilatura)                  |

## インストール

> **Note**: digestkit-core はまだ PyPI に publish されていません。初回リリースまでは umbrella リポジトリの `main` ブランチから git URL 経由でインストールしてください。

```bash
pip install "digestkit-core @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/digestkit-core"
```

[uv](https://docs.astral.sh/uv/) プロジェクトの場合:

```toml
[project]
dependencies = ["digestkit-core>=0.1,<0.2"]

[tool.uv.sources]
digestkit-core = { git = "https://github.com/koki-nakamura22/inboxkit.git", subdirectory = "packages/digestkit-core", branch = "main" }
```

通常エンドユーザーが `digestkit-core` に直接依存することはありません。`digestkit` または `rag-ingest` を install すれば依存解決で自動的に入ります。

## 中立性契約

`digestkit-core` は以下への依存を**禁止**します:

- LLM クライアント (`litellm`、各プロバイダ SDK)
- ベクトルストア (`sqlite-vec` 等)
- 通知系 (SMTP / Slack SDK)
- `digestkit` / `rag-ingest` 自身 (逆方向依存禁止)

これは CI (`.github/workflows/digestkit-core-inspection.yml`) で機械的に強制されます。
背景は [ADR-0003](../../docs/adr/0003-digestkit-core-extraction-policy.md) を参照。

## コントリビュート

開発セットアップ / lint・format・typecheck ターゲット / pre-commit フックについては umbrella の [CONTRIBUTING.md](../../CONTRIBUTING.md) を参照してください。
