[English](README.md) | **日本語**

# inboxkit

> 個人の "inbox" を取り込むためのツール群を束ねる umbrella monorepo。読み物 / 書き物 / シグナルが既に溜まっている場所 (Notion / Web / PDF / Slack / メール ...) からコンテンツを取得し、要約 → RAG 取り込み → 最終的に AI コーディングエージェントから再利用できる形へ変換する。

## Philosophy

自分の思考を実際に形作っている情報は、すでに inbox に溜まっています — 保存した Notion ページ、読みかけの PDF、夜中にブックマークした Web 記事、Slack スレッド、メール。それらが「あとから (あるいは AI エージェント越しに) 問い直せる場所」に戻ってくることは、普通はありません。`inboxkit` はこれらの inbox を一級のデータソースとして扱い、再利用可能な成果物 — 人間向け digest / RAG コーパス / (将来的に) MCP 経由で引ける個人ナレッジベース — へ変換する Python パッケージ群です。

各パッケージは単独で install して使えます。umbrella の存在意義は、共通抽象 (`Source` / `Extractor` / cache / sink) を「複数の実コール元で検証されてから初めて」抽出する (rule of three) ための土台を提供することにあります。

## Packages

| パッケージ | 役割 | Phase | ステータス |
|---|---|---|---|
| [digestkit](./packages/digestkit) | 1:1 パイプライン: fetch → extract → LLM 要約 → sink | Phase 1 | 進行中 (PyPI 公開前) |
| digestkit-core | `Source` / `Extractor` 共通抽象。2 番目の消費者 (`rag-ingest`) が必要になった時点で抽出 | Phase 2 | 未着手 |
| rag-ingest | 1:N パイプライン: fetch → extract → chunk → embed → vector store | Phase 2 | 未着手 |
| personal-rag | SQLite + sqlite-vec ストア + MCP サーバ。AI コーディングエージェントから個人コーパスを問い合わせる | Phase 3 | 未着手 |

命名のズレについて: umbrella リポジトリ名は `inboxkit` ですが、Phase 1 で PyPI 公開するパッケージ名は `digestkit` です。背景と根拠は [packages/digestkit/README.md](./packages/digestkit/README.md) およびプロジェクトの PRD を参照。

## リポジトリ構成

```
inboxkit/
├── README.md                       ← English 版
├── README.ja.md                    ← 本ファイル (日本語版 umbrella 全体像)
├── CONTRIBUTING.md                 ← 開発セットアップ (English)
├── CONTRIBUTING.ja.md              ← 日本語版
├── Makefile                        ← lint / format / typecheck / test 統一ターゲット
├── pyproject.toml                  ← uv workspace ルート
├── packages/
│   └── digestkit/                  ← Phase 1 パッケージ (単独 install 可)
│       ├── README.md
│       ├── pyproject.toml
│       ├── src/digestkit/
│       └── tests/
└── docs/                           ← umbrella レベルドキュメント (フロー情報は .gitignore、確定ストックのみ昇格)
```

Phase 2 / 3 のパッケージは追加時に `packages/` 配下へ同列に並びます。

## 共通 core 抽出ポリシー

`digestkit-core` を先回りで抽出することはしません。今 1 パッケージしか存在しない (`digestkit`) 段階で、まだ生まれてもいない兄弟のために抽象化のコストを払うべきではないからです。

3 段階で進めます:

1. **Phase 1 (現在)** — `digestkit` 単独。core なし。
2. **Phase 2** — `rag-ingest` を追加。`Source` / `Extractor` 部分の重複を**意図的に**残し、2 つの実コール元から共通サーフェスを観察してから `digestkit-core` を抽出する (rule of three)。
3. **Phase 3** — `personal-rag` が `rag-ingest` の生成コーパスを消費し、MCP 経由で AI コーディングエージェントへ公開する。

共通化候補 (Phase 2 のウォッチリスト):

- `Source` / `Extractor` プロトコルとその共通実装 (Notion DB / web / PDF / ローカルディレクトリ)
- `SeenStore` / dedup-key 抽象
- dotenv + redacted logging のボイラープレート
- CLI 配管 (entrypoint / 設定ロード)

恐らく共通化しないもの (パッケージ専有のまま):

- `Summarizer` (digestkit 専用 — 1:1 LLM 呼び出し)
- `Embedder` / `Chunker` / vector-store sink (rag-ingest 専用 — 1:N フロー)
- MCP サーバ実装 (personal-rag 専用)

## Privacy / Security

これらのツールは個人コンテンツを LLM / embedding プロバイダ (Anthropic / OpenAI / Google 等) に送信します。

このパッケージ群すべてで強制される共通ルール:

- **API キーは環境変数経由でのみ読み込む** (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 等)。`python-dotenv` でロードし、ログ出力前に redact する。
- **ソース側の認証情報 (Notion / Slack トークン等) も同様に環境変数経由**。ハードコード禁止、キャッシュ・出力にも書き出さない。
- **PII のマスクは原則ソース境界の責務**。`inboxkit` 自体はメール / 名前 / メッセージ著者をフェッチ後に伏せたりはしない — 第三者 LLM に流せないコンテンツは `inboxkit` に流さない。
- **`docs/` および `tasks.json` は .gitignore** されています (フロー情報のため、詳細は CONTRIBUTING 参照)。確定したストック文書は明示的に正規位置へ昇格させる運用です。

パッケージ固有の Privacy 詳細は各パッケージ README に記載します。

## Install / Usage

各パッケージは単独で install / 実行できます。インストール手順 / 設定 / サンプルはパッケージ README を参照:

- [digestkit — README](./packages/digestkit/README.md)

## Contributing

開発セットアップ (uv workspace / pre-commit hook / Makefile ターゲット) は [CONTRIBUTING.ja.md](./CONTRIBUTING.ja.md) を参照してください。

## License

Apache License 2.0 — [LICENSE](LICENSE) を参照。
