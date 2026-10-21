"""Preview and apply version-one JSON exports."""

import sqlite3
from pathlib import Path
from typing import Annotated

import typer

from odometer.db.session import get_database_path
from odometer.services.import_service import import_data


def import_json(
    source: Path,
    conflict_policy: Annotated[str, typer.Option(help="Required policy: reject (append only).")],
    dry_run: Annotated[bool, typer.Option(help="Validate without writes or backup.")] = False,
    backup: Annotated[
        Path | None, typer.Option(help="Save a SQLite backup first; abort on failure.")
    ] = None,
) -> None:
    """Import v1 vehicles/fuel/expenses, preserving IDs; reminders are outside v1."""
    try:
        result = import_data(
            source,
            get_database_path(),
            conflict_policy=conflict_policy,
            dry_run=dry_run,
            backup=backup,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        typer.echo(f"Import failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    for name in ("vehicles", "fuel", "expenses"):
        typer.echo(f"{name}: {result.counts.get(name, 0)}")
    for error in result.errors:
        typer.echo(error, err=True)
    if result.errors:
        raise typer.Exit(1)
    typer.echo("Preview valid; no changes." if dry_run else "Import committed.")
