from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import click

from rag_ingest.exceptions import ConfigurationError
from rag_ingest.ingester import Ingester, RunResult


def _load_module(module_path: str) -> ModuleType | None:
    path = Path(module_path)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _find_ingester_subclasses(module: ModuleType) -> list[type[Ingester]]:
    return [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type) and obj is not Ingester and issubclass(obj, Ingester)
    ]


@click.group()
def cli() -> None:
    """rag-ingest CLI."""


@cli.command()
@click.argument("module_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--force", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--limit", type=int, default=None)
def run(module_path: str, force: bool, dry_run: bool, limit: int | None) -> None:
    """Run Ingester subclass found in MODULE_PATH."""
    module = _load_module(module_path)
    if module is None:
        click.echo(f"error: cannot load module from {module_path}", err=True)
        sys.exit(3)

    subclasses = _find_ingester_subclasses(module)
    if len(subclasses) == 0:
        click.echo("error: no Ingester subclass found", err=True)
        sys.exit(3)
    if len(subclasses) > 1:
        names = [c.__name__ for c in subclasses]
        click.echo(f"error: multiple Ingester subclasses found: {names}", err=True)
        sys.exit(3)

    ingester = subclasses[0]()

    try:
        result: RunResult = ingester.run(force=force, dry_run=dry_run, limit=limit)
    except ConfigurationError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(3)

    click.echo(
        f"processed={result.processed_sources}, "
        f"chunks={result.chunk_count}, "
        f"skipped={result.skipped_count}, "
        f"failures={len(result.failures)}, "
        f"dry_run_chunks={result.dry_run_chunks}"
    )

    if result.failures:
        if result.processed_sources > 0 or result.dry_run_chunks > 0:
            sys.exit(1)
        sys.exit(2)


def main() -> None:
    cli()
