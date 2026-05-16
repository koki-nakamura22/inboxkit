**English** | [日本語](CONTRIBUTING.ja.md)

# Contributing to inboxkit

## Development setup

This repository is developed with [uv](https://docs.astral.sh/uv/) workspaces on Python 3.11+.

### 1. Install dependencies

```bash
uv sync --all-packages --all-extras
```

### 2. Enable the pre-commit hook (one-time setup)

Runs the same lint / typecheck checks as CI on every local `git commit`.

```bash
make install-hooks
```

Which is equivalent to:

```bash
uv tool install pre-commit
uv tool run pre-commit install
```

From here on, `git commit` triggers the hooks defined in `.pre-commit-config.yaml`,
enforcing:

- `make lint`         (= `uv run ruff check packages/`)
- `make format-check` (= `uv run ruff format --check packages/`)
- `make typecheck`    (= `uv run pyright packages/`)

All of these invoke the same Makefile targets as CI (`.github/workflows/ci.yml`),
so if it passes locally it passes in CI.

### 3. When a hook fails

- **`ruff format --check` failed**: run `make format` to auto-format, then re-commit.
- **`ruff check` failed**: follow the message, or run `uv run ruff check --fix packages/`.
- **`pyright` failed**: fix the types. Only as a last resort, scope a `# pyright: ignore[<rule>]` to the specific line.

### 4. Escape hatch

If you need to bypass `pre-commit` temporarily (e.g. to stash a WIP commit):

```bash
git commit --no-verify
```

You must still run `make check` before the final commit / push. Skipping with
`--no-verify` and pushing will only push the same failure into CI.

## Common Make targets

```bash
make help          # list available targets
make check         # lint + format-check + typecheck (same as CI lint/typecheck)
make format        # auto-format with ruff
make test          # pytest (excluding demonstration / needs_network)
```

## Related issues / PRs

- Background for adopting pre-commit: [Issue #15](https://github.com/koki-nakamura22/inboxkit/issues/15)
- The formatting miss that triggered it: [PR #14](https://github.com/koki-nakamura22/inboxkit/pull/14)
