"""Portability invariants, publication safety and CLI integration."""

import csv
import json
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session
from typer.testing import CliRunner

from odometer.cli.app import app
from odometer.db.session import get_database_path
from odometer.models import Expense, ExpenseCategory, FuelLog, Vehicle, VehicleStatus
from odometer.services.portability_service import backup_database, export_data


def test_exports_preserve_records(session: Session, tmp_path: Path) -> None:
    vehicle = Vehicle(
        registration="TEST",
        normalised_registration="TEST",
        initial_mileage=1,
        status=VehicleStatus.ARCHIVED,
        purchase_price_pence=9007199254740993,
    )
    session.add(vehicle)
    session.commit()
    fuel = FuelLog(
        vehicle_id=vehicle.id,
        date=date(2026, 1, 1),
        odometer_miles=2,
        litres=1.1,
        total_cost_pence=123,
        is_full_tank=False,
        notes="é,\nquoted",
    )
    expense = Expense(
        vehicle_id=vehicle.id,
        date=date(2026, 1, 1),
        category=ExpenseCategory.FUEL,
        amount_pence=127,
    )
    session.add_all([fuel, expense])
    session.commit()
    source = get_database_path()
    before = source.read_bytes()
    destination = tmp_path / "export.json"
    export_data(source, destination)
    data = json.loads(destination.read_text())
    assert data["format_version"] == 1
    assert data["vehicles"][0]["purchase_price_pence"] == 9007199254740993
    assert data["vehicles"][0]["status"] == "ARCHIVED"
    assert data["fuel"][0]["vehicle_id"] == vehicle.id
    assert data["fuel"][0]["id"] == fuel.id
    assert data["fuel"][0]["is_full_tank"] is False
    assert data["expenses"][0]["amount_pence"] == 127
    for dataset in ("vehicles", "fuel", "expenses"):
        output = tmp_path / f"{dataset}.csv"
        export_data(source, output, dataset)
        with output.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 1
        assert set(rows[0]) == set(data[dataset][0])
        assert rows[0]["id"] == data[dataset][0]["id"]
    assert source.read_bytes() == before


def test_backup_includes_wal_and_preserves_source(session: Session, tmp_path: Path) -> None:
    source = get_database_path()
    with closing(sqlite3.connect(source)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE extra (value INTEGER)")
        writer.execute("INSERT INTO extra VALUES (123)")
        writer.commit()
        before = source.read_bytes()
        destination = tmp_path / "backup.db"
        backup_database(source, destination)
        with closing(sqlite3.connect(destination)) as restored:
            assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert restored.execute("SELECT * FROM extra").fetchall() == [(123,)]
        assert source.read_bytes() == before
        assert writer.execute("SELECT * FROM extra").fetchall() == [(123,)]


@pytest.mark.parametrize("operation", [export_data, backup_database])
def test_no_clobber_and_failures(operation, session: Session, tmp_path: Path) -> None:
    source = get_database_path()
    before = source.read_bytes()
    existing = tmp_path / "existing"
    existing.write_text("keep")
    for destination in (existing, source):
        with pytest.raises(FileExistsError):
            operation(source, destination)
    assert existing.read_text() == "keep"
    assert source.read_bytes() == before
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        operation(missing, tmp_path / "out")
    assert not missing.exists()
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".odometer-*"))


def test_cli(session: Session, tmp_path: Path) -> None:
    runner = CliRunner()
    for index, command in enumerate(
        (["export", "json"], ["export", "csv", "vehicles"], ["backup"])
    ):
        destination = str(tmp_path / str(index))
        assert runner.invoke(app, [*command, destination]).exit_code == 0
        assert runner.invoke(app, [*command, destination]).exit_code == 1
    assert runner.invoke(app, ["export", "csv", "invalid", "unused"]).exit_code != 0


def test_empty_exports_and_invalid_source(session: Session, tmp_path: Path) -> None:
    source = get_database_path()
    output = tmp_path / "empty.csv"
    export_data(source, output, "fuel")
    assert "total_cost_pence" in output.read_text()
    assert len(output.read_text().splitlines()) == 1
    with pytest.raises(ValueError):
        export_data(source, tmp_path / "invalid", "unknown")
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_text("not a database")
    with pytest.raises(sqlite3.DatabaseError):
        backup_database(corrupt, tmp_path / "backup.db")
    assert not (tmp_path / "backup.db").exists()
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "absent")
    with pytest.raises(FileExistsError):
        export_data(source, link)
    assert not (tmp_path / "absent").exists()
