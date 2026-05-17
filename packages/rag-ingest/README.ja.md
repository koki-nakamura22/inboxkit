[English](README.md) | **日本語**

# rag-ingest

[![CI](https://img.shields.io/github/actions/workflow/status/koki-nakamura22/inboxkit/rag-ingest-ci.yml?label=CI)](https://github.com/koki-nakamura22/inboxkit/actions/workflows/rag-ingest-ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](https://opensource.org/licenses/Apache-2.0)
![Python](https://img.shields.io/pypi/pyversions/rag-ingest?label=python)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

機械向け 1:N 取り込みパイプライン:
**fetch → extract → chunk → embed → vector sink**

`rag-ingest` は [inboxkit](https://github.com/koki-nakamura22/inboxkit) umbrella monorepo の Phase 2 コンポーネントです。[digestkit-core](../digestkit-core) から `Source` / `Extractor` 抽象を再利用し、その後段に chunking / embedding / ベクトルストア書き込み層を加え、個人 RAG コーパス構築に適した形に整えます。

## パイプライン構造

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

- **1 Source item = 1 transaction**: 部分失敗の境界は item 単位
- item 単位の失敗は集約され、最初のエラーで全体を中断する代わりにパイプラインは継続
- `IngestContext` が `embedder_provider` / `embedder_model` / `chunker_config` / `extractor_version` / `extracted_at` を sink に伝播し、下流ツールが provenance を判別できるようにする

## インストール

> **Note**: rag-ingest はまだ PyPI に publish されていません。初回リリースまでは umbrella リポジトリの `main` ブランチから git URL 経由で install してください。

```bash
pip install "rag-ingest @ git+https://github.com/koki-nakamura22/inboxkit.git@main#subdirectory=packages/rag-ingest"
```

[uv](https://docs.astral.sh/uv/) プロジェクトの場合:

```toml
[project]
dependencies = ["rag-ingest"]

[tool.uv.sources]
rag-ingest = { git = "https://github.com/koki-nakamura22/inboxkit.git", subdirectory = "packages/rag-ingest", branch = "main" }
```

`digestkit-core` は推移的依存として自動的に入ります。

## Quickstart

`.env` に embedding プロバイダの API key を設定:

```
OPENAI_API_KEY=sk-...
```

ingester を定義して実行:

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

設定駆動 / テスト用途では `digestkit.Digester` と同様に `Ingester(...)` を kwarg 直接渡しでも構築できます。

## CLI

```bash
rag-ingest run my_ingester.py
```

フラグ:

- `--dry-run` — `extract` と `chunk` だけ実行。embedding と sink 書き込みはスキップ
- `--limit N` — 処理する Source item を最大 N 件に制限

## コンポーネント

| モジュール                            | クラス / 関数             | 補足                                                                  |
| ------------------------------------- | ------------------------- | --------------------------------------------------------------------- |
| `rag_ingest.ingester`                 | `Ingester` / `RunResult`  | パイプライン駆動、dry-run 対応、item 単位の失敗記録                   |
| `rag_ingest.chunkers.fixed_size`      | `FixedSizeChunker`        | 固定長 chunk (token / char 単位) + overlap                            |
| `rag_ingest.embedders.llm`            | `LLMEmbedder`             | LiteLLM ベースの embedder。バッチ呼び出し                             |
| `rag_ingest.sinks.sqlite_vec`         | `SQLiteVecSink`           | sqlite-vec writer。Source 1 件 = 1 transaction                        |
| `rag_ingest.protocols`                | `Chunker` / `Embedder` / `VectorSink` | `runtime_checkable` Protocol                              |

## digestkit との関係

両パッケージは [digestkit-core](../digestkit-core) を介して `Source` / `Extractor` 抽象を共有します。digestkit は**人間向け要約** (1:1) を生成し、rag-ingest は**機械が検索するための chunk + embedding** (1:N) を生成します。両者は意図的に独立しています: digestkit の圧縮された要約を rag-ingest の入力にしては**いけません** — 検索品質に必要な情報が失われます。両方の出力が必要なら、同じ Source から両者を並列で走らせてください。

## オプション依存

base install で完全なパイプラインに必要なものはすべて入ります (`litellm` / `tiktoken` / `sqlite-vec` / `python-dotenv` / `click`)。Source / Extractor 用の SDK (`pypdf` / `trafilatura` / `notion-client`) は `digestkit-core` から推移的に入ります。

## コントリビュート

開発セットアップ / lint・format・typecheck ターゲット / pre-commit フックについては umbrella の [CONTRIBUTING.md](../../CONTRIBUTING.md) を参照してください。
