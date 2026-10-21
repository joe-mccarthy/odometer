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


INTEGER_FIELDS = [
    ("vehicles", "year"),
    ("vehicles", "initial_mileage"),
    ("vehicles", "purchase_price_pence"),
    ("fuel", "odometer_miles"),
    ("fuel", "total_cost_pence"),
    ("expenses", "amount_pence"),
    ("expenses", "odometer_miles"),
]


@pytest.mark.parametrize("table,field", INTEGER_FIELDS)
@pytest.mark.parametrize("value", [2**63, -(2**63) - 1])
@pytest.mark.parametrize("existing", [False, True])
def test_int64_overflow_rejected_before_side_effects(bundle, table, field, value, existing):
    from odometer.db.bootstrap import initialise_database
    from odometer.services.import_service import preview_import

    source, target, data = bundle
    target = target.parent / "missing-parent" / target.name
    if existing:
        initialise_database(target)
    before = target.read_bytes() if existing else None
    data[table][0][field] = value
    source.write_text(json.dumps(data))
    backup = target.parent / "backup.db"
    preview = preview_import(source, target, "reject")
    assert any(f"{table}[0].{field}:" in e and "signed 64-bit" in e for e in preview.errors)
    for dry_run in (True, False):
        result = import_data(
            source, target, conflict_policy="reject", dry_run=dry_run, backup=backup
        )
        assert result.errors == preview.errors
        assert not backup.exists()
        if existing:
            assert target.read_bytes() == before
        else:
            assert not target.exists()
            assert not target.parent.exists()


@pytest.mark.parametrize("table,field", INTEGER_FIELDS)
@pytest.mark.parametrize("value", [-(2**63), 2**63 - 1])
def test_int64_boundaries_respect_domain_rules(bundle, table, field, value):
    source, target, data = bundle
    # One fuel row keeps the mileage boundary independent of history ordering.
    data["fuel"] = data["fuel"][:1]
    data[table][0][field] = value
    if field == "initial_mileage" and value >= 0:
        data["fuel"][0]["odometer_miles"] = value
        data["expenses"][0]["odometer_miles"] = value
    source.write_text(json.dumps(data))
    result = import_data(source, target, conflict_policy="reject", dry_run=True)
    valid = value >= 0 or field == "year"
    assert bool(result.errors) is not valid
    assert not any("signed 64-bit" in e for e in result.errors)
    applied = import_data(source, target, conflict_policy="reject")
    assert applied.errors == result.errors
    if valid:
        output = target.with_suffix(".json")
        export_data(target, output)
        assert json.loads(output.read_text())[table][0][field] == value
    else:
        assert not target.exists()


@pytest.mark.parametrize("dry_run", [False, True])
def test_cli_int64_overflow_is_located_and_has_no_side_effects(bundle, monkeypatch, dry_run):
    source, target, data = bundle
    target = target.parent / "missing-parent" / target.name
    monkeypatch.setenv("ODOMETER_DB_PATH", str(target))
    data["expenses"][0]["amount_pence"] = 9223372036854775808
    source.write_text(json.dumps(data))
    backup = target.parent / "backup.db"
    args = ["import", str(source), "--conflict-policy", "reject", "--backup", str(backup)]
    if dry_run:
        args.append("--dry-run")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert "expenses[0].amount_pence:" in result.output
    assert "signed 64-bit" in result.output
    assert not target.parent.exists()


@pytest.mark.parametrize("table,field", INTEGER_FIELDS)
def test_integer_fields_still_reject_booleans(bundle, table, field):
    source, target, data = bundle
    data[table][0][field] = True
    source.write_text(json.dumps(data))
    result = import_data(source, target, conflict_policy="reject")
    assert result.errors
    assert not target.exists()


def test_cli_valid_int64_boundary_import(bundle, monkeypatch):
    source, target, data = bundle
    monkeypatch.setenv("ODOMETER_DB_PATH", str(target))
    data["expenses"][0]["amount_pence"] = 2**63 - 1
    source.write_text(json.dumps(data))
    result = CliRunner().invoke(app, ["import", str(source), "--conflict-policy", "reject"])
    assert result.exit_code == 0, result.output
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT amount_pence FROM expense").fetchone() == (2**63 - 1,)
        assert db.execute("SELECT DISTINCT is_full_tank FROM fuellog ORDER BY 1").fetchall() == [
            (0,),
            (1,),
        ]


PERSISTED_FIELDS = [
    (table, field)
    for table, model in (("vehicles", Vehicle), ("fuel", FuelLog), ("expenses", Expense))
    for field in model.model_fields
]


@pytest.mark.parametrize("table,field", PERSISTED_FIELDS)
@pytest.mark.parametrize("existing", [False, True])
def test_all_persisted_fields_required_before_side_effects(bundle, table, field, existing):
    from odometer.db.bootstrap import initialise_database

    source, target, data = bundle
    target = target.parent / "missing-parent" / target.name
    if existing:
        initialise_database(target)
    before = target.read_bytes() if existing else None
    del data[table][0][field]
    source.write_text(json.dumps(data))
    backup = target.parent / "backup.db"
    for dry_run in (True, False):
        result = import_data(
            source, target, conflict_policy="reject", dry_run=dry_run, backup=backup
        )
        assert f"{table}[0].{field}: persisted field is required" in result.errors
        assert not backup.exists()
        if existing:
            assert target.read_bytes() == before
        else:
            assert not target.parent.exists()


@pytest.mark.parametrize("backdated", [False, True])
def test_normal_logging_histories_roundtrip_losslessly(tmp_path, backdated):
    from sqlmodel import Session, create_engine

    from odometer.db.bootstrap import initialise_database
    from odometer.services.fuel_service import FuelService

    source_db = tmp_path / "source.db"
    initialise_database(source_db)
    with Session(create_engine(f"sqlite:///{source_db}")) as session:
        vehicle = Vehicle(
            registration="AB12 CDE",
            normalised_registration="AB12CDE",
            initial_mileage=0,
            fuel_tank_litres=60,
        )
        session.add(vehicle)
        session.commit()
        session.refresh(vehicle)
        service = FuelService(session)
        for mileage, identifier, full in [(100, "z", True), (200, "a", False), (300, "m", True)]:
            row = service.add_fuel_log(
                vehicle_identifier=vehicle.id,
                litres=20,
                total_cost_pence=3000,
                odometer_miles=mileage,
                date_=date(2026, 1, 1 if backdated and mileage == 300 else 2),
                is_full_tank=full,
            )
            # Random UUID order and tied timestamps provide no insertion chronology.
            row.id = identifier
            session.add(row)
            session.commit()
        # Notes-only corrections of such persisted histories must still work.
        service.update_fuel_log("a", notes="preserved partial")
    source = tmp_path / "input.json"
    export_data(source_db, source)
    target = tmp_path / "target.db"
    assert not import_data(source, target, conflict_policy="reject", dry_run=True).errors
    assert not target.exists()
    assert not import_data(source, target, conflict_policy="reject").errors
    output = tmp_path / "output.json"
    export_data(target, output)
    assert json.loads(output.read_text()) == json.loads(source.read_text())
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT is_full_tank FROM fuellog WHERE id='a'").fetchone() == (0,)
