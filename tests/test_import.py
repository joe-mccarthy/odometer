"""Atomic version-one import regression tests."""

import json
import sqlite3
from datetime import date

import pytest
from typer.testing import CliRunner

from odometer.cli.app import app
from odometer.models import Expense, FuelLog, Vehicle
from odometer.models.enums import ExpenseCategory
from odometer.services.import_service import import_data
from odometer.services.portability_service import export_data


@pytest.fixture
def bundle(tmp_path):
    vehicle = Vehicle(
        registration="AB12 CDE",
        normalised_registration="AB12CDE",
        initial_mileage=100,
        fuel_tank_litres=60,
    )
    fuel = [
        FuelLog(
            id=str(i),
            vehicle_id=vehicle.id,
            date=date(2026, 1, i + 1),
            odometer_miles=100 + i * 100,
            litres=20,
            total_cost_pence=3000,
            is_full_tank=i != 1,
        )
        for i in range(3)
    ]
    expense = Expense(
        vehicle_id=vehicle.id,
        date=date(2026, 1, 2),
        category=ExpenseCategory.FUEL,
        amount_pence=3000,
    )
    data = {
        "format_version": 1,
        "vehicles": [vehicle.model_dump(mode="json")],
        "fuel": [r.model_dump(mode="json") for r in reversed(fuel)],
        "expenses": [expense.model_dump(mode="json")],
    }
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    return source, tmp_path / "target.db", data


def test_roundtrip_preview_and_collisions(bundle):
    source, target, data = bundle
    assert not import_data(source, target, conflict_policy="reject", dry_run=True).errors
    assert not target.exists()
    assert not import_data(source, target, conflict_policy="reject").errors
    output = target.with_suffix(".json")
    export_data(target, output)
    actual = json.loads(output.read_text())
    for key in ("vehicles", "fuel", "expenses"):
        assert sorted(actual[key], key=lambda r: r["id"]) == sorted(
            data[key], key=lambda r: r["id"]
        )
    before = target.read_bytes()
    assert import_data(source, target, conflict_policy="reject").errors
    assert target.read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(format_version=2),
        lambda d: d["fuel"].append(d["fuel"][0]),
        lambda d: d["fuel"][0].update(vehicle_id="orphan"),
        lambda d: d["fuel"][0].update(total_cost_pence=1.5),
        lambda d: d["fuel"][0].update(total_cost_pence=True),
        lambda d: d["fuel"][0].update(date="bad"),
        lambda d: d["fuel"][0].update(litres=100),
        lambda d: d["fuel"][0].update(odometer_miles=99),
        lambda d: d["expenses"][0].update(category="BAD"),
        lambda d: d["expenses"][0].update(amount_pence=-1),
        lambda d: d["vehicles"][0].update(fuel_tank_litres=-1),
    ],
)
def test_invalid_whole_file_has_no_writes(bundle, mutation):
    source, target, data = bundle
    mutation(data)
    source.write_text(json.dumps(data))
    result = import_data(source, target, conflict_policy="reject")
    assert result.errors
    assert result.counts["vehicles"] == 1
    assert not target.exists()


def test_transaction_rollback_and_backup_failure(bundle):
    source, target, _ = bundle
    from odometer.db.bootstrap import initialise_database

    initialise_database(target)
    with sqlite3.connect(target) as db:
        db.execute(
            "CREATE TRIGGER fail BEFORE INSERT ON expense "
            "BEGIN SELECT RAISE(ABORT, 'late failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        import_data(source, target, conflict_policy="reject")
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT count(*) FROM vehicle").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM fuellog").fetchone() == (0,)
    with pytest.raises(OSError):
        import_data(source, target, conflict_policy="reject", backup=source)


def test_cli_requires_policy_and_dry_run_no_backup(bundle, monkeypatch):
    source, target, _ = bundle
    monkeypatch.setenv("ODOMETER_DB_PATH", str(target))
    runner = CliRunner()
    assert runner.invoke(app, ["import", str(source)]).exit_code == 2
    backup = target.with_suffix(".backup")
    result = runner.invoke(
        app,
        [
            "import",
            str(source),
            "--conflict-policy",
            "reject",
            "--dry-run",
            "--backup",
            str(backup),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "fuel: 3" in result.output
    assert not target.exists() and not backup.exists()


def test_registration_conflict_and_backup_success(bundle):
    source, target, data = bundle
    assert not import_data(source, target, conflict_policy="reject").errors
    data["vehicles"][0]["id"] = "other"
    data["fuel"] = []
    data["expenses"] = []
    source.write_text(json.dumps(data))
    assert any(
        "registration" in e for e in import_data(source, target, conflict_policy="reject").errors
    )
    data["vehicles"][0].update(registration="ZZ99 ZZZ", normalised_registration="ZZ99ZZZ")
    source.write_text(json.dumps(data))
    backup = target.with_suffix(".backup")
    assert not import_data(source, target, conflict_policy="reject", backup=backup).errors
    with sqlite3.connect(backup) as db:
        assert db.execute("SELECT count(*) FROM vehicle").fetchone() == (1,)
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT count(*) FROM vehicle").fetchone() == (2,)


def test_conflicts_revalidated_after_preview(bundle, monkeypatch):
    source, target, _ = bundle
    from odometer.db.bootstrap import initialise_database

    initialise_database(target)
    from odometer.services import import_service

    original = import_service.preview_import

    def racing_preview(*args):
        preview = original(*args)
        monkeypatch.setattr(import_service, "preview_import", original)
        assert not import_service.import_data(source, target, conflict_policy="reject").errors
        return preview

    monkeypatch.setattr(import_service, "preview_import", racing_preview)
    assert import_data(source, target, conflict_policy="reject").errors
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT count(*) FROM vehicle").fetchone() == (1,)
