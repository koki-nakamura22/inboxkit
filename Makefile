# inboxkit workspace 共通タスク
#
# CI (.github/workflows/ci.yml) とローカル pre-commit hook
# (.pre-commit-config.yaml) は本ファイルのターゲットを共通の入口として使う。
# CI とローカルのチェック内容がズレないように、コマンド実体はここに集約する。

UV ?= uv
PACKAGES := packages/

.PHONY: help lint format format-check typecheck check test install-hooks

help:
	@echo "Targets:"
	@echo "  lint           - ruff check $(PACKAGES)"
	@echo "  format         - ruff format $(PACKAGES) (rewrites files)"
	@echo "  format-check   - ruff format --check $(PACKAGES)"
	@echo "  typecheck      - pyright $(PACKAGES)"
	@echo "  check          - lint + format-check + typecheck (= CI lint/typecheck と同等)"
	@echo "  test           - pytest packages/digestkit/tests"
	@echo "  install-hooks  - install pre-commit hooks (one-shot setup)"

lint:
	$(UV) run ruff check $(PACKAGES)

format:
	$(UV) run ruff format $(PACKAGES)

format-check:
	$(UV) run ruff format --check $(PACKAGES)

typecheck:
	$(UV) run pyright $(PACKAGES)

check: lint format-check typecheck

test:
	$(UV) run pytest packages/digestkit/tests -m "not demonstration and not needs_network"

# 初回セットアップ: pre-commit を uv tool に入れて hook を有効化する。
# 個人環境ごとに 1 度だけ実行すれば良い。
install-hooks:
	$(UV) tool install pre-commit
	$(UV) tool run pre-commit install
