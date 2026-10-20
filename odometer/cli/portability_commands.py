"""Portable export and online backup commands."""

import sqlite3
from enum import StrEnum
from pathlib import Path

import typer

from odometer.db.session import get_database_path
from odometer.services.portability_service import backup_database, export_data

export_app = typer.Typer(help="Export all records, including inactive vehicles.")


class Dataset(StrEnum):
    VEHICLES = "vehicles"
    FUEL = "fuel"
    EXPENSES = "expenses"


def _run(destination: Path, dataset: str | None = None, *, backup: bool = False) -> None:
    try:
        if backup:
            backup_database(get_database_path(), destination)
        else:
            export_data(get_database_path(), destination, dataset)
    except (OSError, ValueError, sqlite3.Error) as error:
        typer.echo(f"Unable to write output: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Saved: {destination}")


@export_app.command("json")
def export_json(destination: Path) -> None:
    """Write versioned JSON with all vehicles, fuel logs and expenses."""
    _run(destination)


@export_app.command("csv")
def export_csv(dataset: Dataset, destination: Path) -> None:
    """Write one CSV table with identifiers and integer-pence amounts."""
    _run(destination, dataset.value)


def backup(destination: Path) -> None:
    """Write an integrity-checked SQLite online backup; never overwrite a file."""
    _run(destination, backup=True)
