# Contributing to inboxkit

## Development setup

本リポジトリは [uv](https://docs.astral.sh/uv/) workspace + Python 3.11 以上で開発します。

### 1. 依存セットアップ

```bash
uv sync --all-packages --all-extras
```

### 2. pre-commit hook の有効化 (初回 1 回のみ)

ローカル `git commit` 時に CI lint / typecheck と同等のチェックを自動実行します。

```bash
make install-hooks
```

これは以下と等価です:

```bash
uv tool install pre-commit
uv tool run pre-commit install
```

これで以降の `git commit` では `.pre-commit-config.yaml` のフックが走り、以下が
強制されます:

- `make lint`         (= `uv run ruff check packages/`)
- `make format-check` (= `uv run ruff format --check packages/`)
- `make typecheck`    (= `uv run pyright packages/`)

すべて CI (`.github/workflows/ci.yml`) と同じ Makefile ターゲットを呼ぶため、
ローカルで通れば CI でも通ります。

### 3. 失敗した時

- **ruff format --check が失敗**: `make format` で自動整形してから再 commit
- **ruff check が失敗**: メッセージに従って修正、または `uv run ruff check --fix packages/`
- **pyright が失敗**: 型を直す。緊急で逃したい時のみ `# pyright: ignore[<rule>]` を限定的に

### 4. Escape hatch

`pre-commit` の介入を一時的に逃したい場合 (WIP commit を積みたい等):

```bash
git commit --no-verify
```

ただし最終 commit / push 前には必ず `make check` を通してください。`--no-verify`
で逃したまま push しても CI で同じ内容が落ちます。

## よく使うターゲット

```bash
make help          # 一覧
make check         # lint + format-check + typecheck (= CI lint/typecheck と同等)
make format        # ruff format で自動整形
make test          # pytest (demonstration / needs_network 除外)
```

## 関連 Issue / PR

- pre-commit 導入の経緯: [Issue #15](https://github.com/koki-nakamura22/inboxkit/issues/15)
- 発端となった整形漏れ: [PR #14](https://github.com/koki-nakamura22/inboxkit/pull/14)
