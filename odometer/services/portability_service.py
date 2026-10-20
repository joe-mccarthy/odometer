"""Local, lossless exports and consistent SQLite online backups."""

import csv
import json
import os
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from sqlmodel import SQLModel

from odometer.models import Expense, FuelLog, Vehicle

TABLES: dict[str, type[SQLModel]] = {"vehicles": Vehicle, "fuel": FuelLog, "expenses": Expense}


@contextmanager
def _snapshot(source: Path) -> Iterator[sqlite3.Connection]:
    # mode=ro prevents accidentally creating or migrating the source database.
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as origin:
        snapshot = sqlite3.connect(":memory:")
        try:
            origin.backup(snapshot)
            snapshot.row_factory = sqlite3.Row
            yield snapshot
        finally:
            snapshot.close()


@contextmanager
def _output(destination: Path) -> Iterator[Path]:
    """Publish a complete file atomically without replacing any existing path."""
    descriptor, name = tempfile.mkstemp(prefix=".odometer-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def export_data(source: Path, destination: Path, dataset: str | None = None) -> None:
    """Export versioned JSON, or one CSV table, from a consistent snapshot.

    JSON includes all persisted fields. CSV uses empty cells for null values,
    ISO dates, lowercase booleans, and integer pence for monetary totals.
    """
    if dataset is not None and dataset not in TABLES:
        raise ValueError(f"Unknown dataset: {dataset}")
    with _snapshot(source) as snapshot:
        data = {}
        for name, model in TABLES.items():
            if dataset is None or name == dataset:
                table = {"vehicles": "vehicle", "fuel": "fuellog", "expenses": "expense"}[name]
                rows = snapshot.execute(f'SELECT * FROM "{table}" ORDER BY id')
                data[name] = [
                    model.model_validate(dict(row)).model_dump(mode="json") for row in rows
                ]
    with _output(destination) as temporary:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            if dataset is None:
                json.dump({"format_version": 1, **data}, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            else:
                writer = csv.DictWriter(stream, fieldnames=list(TABLES[dataset].model_fields))
                writer.writeheader()
                for row in data[dataset]:
                    writer.writerow(
                        {
                            key: str(value).lower() if isinstance(value, bool) else value
                            for key, value in row.items()
                        }
                    )


def backup_database(source: Path, destination: Path) -> None:
    """Create and integrity-check a standalone SQLite backup, including WAL data."""
    with _snapshot(source) as snapshot, _output(destination) as temporary:
        with closing(sqlite3.connect(temporary)) as target:
            snapshot.backup(target)
            if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("Backup failed SQLite integrity check")
