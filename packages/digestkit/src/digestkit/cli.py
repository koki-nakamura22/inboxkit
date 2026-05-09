from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from pathlib import Path

from .digester import Digester


def _load_module(module_path: Path) -> object | None:
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="digestkit")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("module", type=Path)
    run_parser.add_argument("--limit", type=int, default=None)
    run_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.command != "run":
        return 3

    if not args.module.exists():
        print(f"error: module file not found: {args.module}", file=sys.stderr)
        return 3

    try:
        module = _load_module(args.module)
    except SyntaxError as e:
        print(f"error: SyntaxError in {args.module}: {e}", file=sys.stderr)
        return 3
    if module is None:
        print(f"error: failed to load {args.module}", file=sys.stderr)
        return 3

    classes = [
        cls
        for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, Digester) and cls is not Digester
    ]
    if len(classes) == 0:
        print("error: no Digester subclass found", file=sys.stderr)
        return 3
    if len(classes) > 1:
        print(
            f"error: multiple Digester subclasses found: {[c.__name__ for c in classes]}",
            file=sys.stderr,
        )
        return 3

    result = classes[0]().run(limit=args.limit, dry_run=args.dry_run)
    print(f"success={result.success} failures={len(result.failures)} skipped={result.skipped}")

    if result.failures and result.success:
        return 1
    if result.failures and not result.success:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
