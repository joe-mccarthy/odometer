"""CLI tests."""

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from odometer.cli.app import app
from odometer.db.bootstrap import initialise_database
from odometer.db.session import DB_PATH_ENV, get_session
from odometer.main import app as main_app
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService
from odometer.tui.app import OdometerTUI

runner = CliRunner()


def test_help_works() -> None:
    """Verify the root CLI help command renders successfully."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Track the true cost" in result.output
    assert main_app is app


def test_config_show_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the config command renders database path information."""
    database_path = Path("/tmp/odometer-test.db")
    monkeypatch.setenv(DB_PATH_ENV, str(database_path))

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "Odometer configuration" in result.output
    assert str(database_path) in result.output
    assert DB_PATH_ENV in result.output


def test_cli_core_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the main CLI flow from database init through summaries and calculations."""
    database_path = tmp_path / "odometer.db"
    monkeypatch.setenv(DB_PATH_ENV, str(database_path))

    assert runner.invoke(app, ["init"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "vehicle",
                "add",
                "--registration",
                "AB12 CDE",
                "--make",
                "Ford",
                "--model",
                "Kuga",
                "--year",
                "2019",
                "--initial-mileage",
                "42000",
                "--fuel-tank-litres",
                "55",
                "--purchase-price",
                "12500",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["vehicle", "list"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "expense",
                "add",
                "--vehicle",
                "AB12CDE",
                "--category",
                "service",
                "--amount",
                "249.99",
                "--mileage",
                "43000",
                "--description",
                "Annual service",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["expense", "list"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "fuel",
                "add",
                "--vehicle",
                "AB12CDE",
                "--litres",
                "45.2",
                "--amount",
                "68.50",
                "--mileage",
                "43420",
                "--station",
                "Tesco",
                "--full",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["fuel", "list"]).exit_code == 0
    assert runner.invoke(app, ["summary", "--vehicle", "AB12CDE"]).exit_code == 0
    assert runner.invoke(app, ["calc", "mpg", "--vehicle", "AB12CDE"]).exit_code == 0


def test_cli_empty_state_messages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify list and calculation commands report empty databases cleanly."""
    database_path = tmp_path / "odometer.db"
    monkeypatch.setenv(DB_PATH_ENV, str(database_path))

    vehicles = runner.invoke(app, ["vehicle", "list"])
    expenses = runner.invoke(app, ["expense", "list"])
    fuel = runner.invoke(app, ["fuel", "list"])
    cost_per_mile = runner.invoke(app, ["calc", "cost-per-mile"])

    assert vehicles.exit_code == 0
    assert "No vehicles found." in vehicles.output
    assert expenses.exit_code == 0
    assert "No expenses found." in expenses.output
    assert fuel.exit_code == 0
    assert "No fuel logs found." in fuel.output
    assert cost_per_mile.exit_code == 0
    assert "No vehicles found." in cost_per_mile.output


def test_cli_reporting_and_vehicle_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise summary, calculation, vehicle detail, and lifecycle CLI output."""
    database_path = tmp_path / "odometer.db"
    monkeypatch.setenv(DB_PATH_ENV, str(database_path))
    initialise_database()

    with get_session() as session:
        vehicle = VehicleService(session).create_vehicle(
            registration="AB12 CDE",
            make="Ford",
            model="Kuga",
            nickname="Family car",
            year=2019,
            initial_mileage=42_000,
            fuel_tank_litres=55,
            purchase_date=date(2025, 6, 1),
            purchase_price_pence=1_250_000,
        )
        ExpenseService(session).add_expense(
            vehicle_identifier=vehicle.id,
            category="service",
            amount_pence=24_999,
            date_=date(2026, 1, 10),
            odometer_miles=43_000,
            description="Annual service",
            vendor="Local garage",
        )
        ExpenseService(session).add_expense(
            vehicle_identifier=vehicle.id,
            category="parking",
            amount_pence=450,
            date_=date(2026, 2, 5),
            odometer_miles=43_250,
        )
        FuelService(session).add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=42.0,
            total_cost_pence=6_300,
            odometer_miles=42_500,
            date_=date(2026, 1, 1),
            station="Shell",
            is_full_tank=True,
        )
        FuelService(session).add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=45.2,
            total_cost_pence=6_850,
            odometer_miles=43_420,
            date_=date(2026, 2, 1),
            station="Tesco",
            is_full_tank=True,
        )

    commands = [
        (
            ["summary", "--vehicle", "AB12CDE", "--from", "2026-01-01", "--to", "2026-12-31"],
            "Cost summary",
        ),
        (["summary", "monthly", "--vehicle", "AB12CDE", "--year", "2026"], "Monthly spend"),
        (["summary", "annual", "--vehicle", "AB12CDE"], "Annual spend"),
        (["summary", "categories", "--vehicle", "AB12CDE"], "Category breakdown"),
        (
            [
                "summary",
                "categories",
                "--vehicle",
                "AB12CDE",
                "--from",
                "2027-01-01",
                "--to",
                "2027-12-31",
            ],
            "No spend found.",
        ),
        (["calc", "mpg", "--vehicle", "AB12CDE"], "UK MPG"),
        (["calc", "cost-per-mile", "--vehicle", "AB12CDE"], "Cost per mile"),
        (["vehicle", "show", "AB12CDE"], "Vehicle AB12 CDE"),
        (["vehicle", "set-fuel-tank", "AB12CDE", "--litres", "60"], "Updated fuel tank"),
        (["vehicle", "list"], "Vehicles"),
        (["vehicle", "archive", "AB12CDE"], "Archived vehicle"),
        (["vehicle", "list"], "No vehicles found."),
        (["vehicle", "list", "--all"], "Vehicles"),
        (["vehicle", "sold", "AB12CDE"], "Marked vehicle"),
        (["vehicle", "list", "--all"], "Vehicles"),
    ]

    for command, expected_output in commands:
        result = runner.invoke(app, command)

        assert result.exit_code == 0
        assert expected_output in result.output


def test_tui_instantiates() -> None:
    """Verify the Textual app can be constructed by the CLI layer."""
    tui = OdometerTUI()

    assert tui is not None


def test_cli_delete_commands_require_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify delete commands cancel on no and delete on yes."""
    database_path = tmp_path / "odometer.db"
    monkeypatch.setenv(DB_PATH_ENV, str(database_path))
    initialise_database()

    with get_session() as session:
        vehicle = VehicleService(session).create_vehicle(
            registration="AB12 CDE",
            initial_mileage=42_000,
            fuel_tank_litres=55,
        )
        expense = ExpenseService(session).add_expense(
            vehicle_identifier=vehicle.id,
            category="service",
            amount_pence=24_999,
            date_=date(2026, 1, 10),
        )
        fuel_log = FuelService(session).add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=45.2,
            total_cost_pence=6_850,
            odometer_miles=43_420,
            date_=date(2026, 1, 12),
        )
        vehicle_id = vehicle.id
        expense_id = expense.id
        fuel_log_id = fuel_log.id

    cancelled_expense = runner.invoke(
        app,
        ["expense", "delete", expense_id],
        input="n\n",
    )
    assert cancelled_expense.exit_code == 0
    assert "Delete cancelled." in cancelled_expense.output

    deleted_expense = runner.invoke(
        app,
        ["expense", "delete", expense_id],
        input="y\n",
    )
    assert deleted_expense.exit_code == 0
    assert f"Deleted expense {expense_id}." in deleted_expense.output

    cancelled_fuel = runner.invoke(
        app,
        ["fuel", "delete", fuel_log_id],
        input="n\n",
    )
    assert cancelled_fuel.exit_code == 0
    assert "Delete cancelled." in cancelled_fuel.output

    deleted_fuel = runner.invoke(
        app,
        ["fuel", "delete", fuel_log_id],
        input="y\n",
    )
    assert deleted_fuel.exit_code == 0
    assert f"Deleted fuel log {fuel_log_id}." in deleted_fuel.output

    with get_session() as session:
        expense = ExpenseService(session).add_expense(
            vehicle_identifier=vehicle_id,
            category="repair",
            amount_pence=15_000,
            date_=date(2026, 1, 20),
        )
        fuel_log = FuelService(session).add_fuel_log(
            vehicle_identifier=vehicle_id,
            litres=40,
            total_cost_pence=6_000,
            odometer_miles=44_000,
            date_=date(2026, 1, 21),
        )
        assert expense.id
        assert fuel_log.id

    cancelled_vehicle = runner.invoke(
        app,
        ["vehicle", "delete", "AB12CDE"],
        input="n\n",
    )
    assert cancelled_vehicle.exit_code == 0
    assert "Delete cancelled." in cancelled_vehicle.output

    deleted_vehicle = runner.invoke(
        app,
        ["vehicle", "delete", "AB12CDE"],
        input="y\n",
    )
    assert deleted_vehicle.exit_code == 0
    assert "Deleted vehicle" in deleted_vehicle.output

    with get_session() as session:
        assert VehicleService(session).list_vehicles(include_inactive=True) == []
        assert ExpenseService(session).list_expenses() == []
        assert FuelService(session).list_fuel_logs() == []
