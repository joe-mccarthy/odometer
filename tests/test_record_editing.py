"""Corrections preserve identity, validate complete history and refresh calculations."""

from datetime import date

import pytest
from typer.testing import CliRunner

from odometer.cli.app import app
from odometer.models.fuel import FuelLog
from odometer.services.exceptions import (
    ExpenseNotFoundError,
    FuelLogNotFoundError,
    InvalidExpenseError,
    InvalidFuelLogError,
)
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService


def history(session):
    vehicle = VehicleService(session).create_vehicle(
        registration="EDIT123", initial_mileage=100, fuel_tank_litres=60
    )
    service = FuelService(session)
    rows = [
        service.add_fuel_log(
            vehicle_identifier=vehicle.id,
            date_=date(2026, 1, day),
            odometer_miles=miles,
            litres=20,
            total_cost_pence=3000,
            is_full_tank=day != 2,
        )
        for day, miles in [(1, 100), (2, 200), (3, 300)]
    ]
    for row in rows:
        session.refresh(row)
    return vehicle, service, rows


def test_edit_identity_partial_money_and_cli(session):
    vehicle, service, rows = history(session)
    original = rows[1].model_dump()
    updated = service.update_fuel_log(rows[1].id, total_cost_pence=1234, is_full_tank=True)
    assert (updated.id, updated.vehicle_id, updated.created_at) == (
        original["id"],
        vehicle.id,
        original["created_at"],
    )
    assert updated.total_cost_pence == 1234
    assert updated.price_per_litre_pence == 61.7
    assert updated.is_full_tank
    runner = CliRunner()
    result = runner.invoke(app, ["fuel", "edit", updated.id, "--amount", "10.01", "--partial"])
    assert result.exit_code == 0, result.output
    session.expire_all()
    assert session.get(FuelLog, updated.id).total_cost_pence == 1001
    assert not session.get(FuelLog, updated.id).is_full_tank
    result = runner.invoke(app, ["fuel", "edit", updated.id, "--amount", "not-money"])
    assert result.exit_code != 0


@pytest.mark.parametrize(
    "changes",
    [
        {"odometer_miles": 99},
        {"odometer_miles": 301},
        {"date_": date(2025, 12, 31)},
        {"date_": date(2026, 1, 4)},
        {"litres": 61},
        {"litres": float("nan")},
        {"total_cost_pence": 0},
        {"total_cost_pence": 1.5},
        {"vehicle_id": "other"},
        {"date_": None},
    ],
)
def test_invalid_correction_does_not_mutate(session, changes):
    _, service, rows = history(session)
    before = [row.model_dump() for row in rows]
    with pytest.raises(InvalidFuelLogError):
        service.update_fuel_log(rows[1].id, **changes)
    session.expire_all()
    after = []
    for row in before:
        loaded = session.get(FuelLog, row["id"])
        after.append(loaded.model_dump())
    assert after == before


def test_backdated_creation_and_reusable_candidate_contract(session):
    vehicle, service, rows = history(session)
    added = FuelLog(
        id=rows[0].id + "a",
        vehicle_id=vehicle.id,
        date=date(2026, 1, 1),
        odometer_miles=150,
        litres=10,
        total_cost_pence=1500,
    )
    service.validate_candidate_history(vehicle, [rows[2], added, rows[0], rows[1]])
    with pytest.raises(InvalidFuelLogError):
        service.add_fuel_log(
            vehicle_identifier=vehicle.id,
            date_=date(2025, 1, 1),
            odometer_miles=250,
            litres=10,
            total_cost_pence=1500,
        )


def test_expense_clear_optional_and_cli(session):
    vehicle, _, _ = history(session)
    service = ExpenseService(session)
    row = service.add_expense(
        vehicle_identifier=vehicle.id,
        category="SERVICE",
        amount_pence=100,
        date_=date(2026, 1, 1),
        odometer_miles=200,
        notes="keep",
    )
    updated = service.update_expense(row.id, amount_pence=1234, odometer_miles=None)
    assert updated.id == row.id and updated.vehicle_id == vehicle.id
    assert updated.notes == "keep" and updated.odometer_miles is None
    for changes in [
        {"amount_pence": 0},
        {"amount_pence": 1.5},
        {"odometer_miles": 99},
        {"category": "bad"},
    ]:
        with pytest.raises(InvalidExpenseError):
            service.update_expense(row.id, **changes)
    result = CliRunner().invoke(
        app, ["expense", "edit", row.id, "--amount", "12.99", "--notes", ""]
    )
    assert result.exit_code == 0, result.output
    session.expire_all()
    assert row.amount_pence == 1299 and row.notes is None
    with pytest.raises(ExpenseNotFoundError):
        service.update_expense("missing", amount_pence=123)
    with pytest.raises(FuelLogNotFoundError):
        FuelService(session).update_fuel_log("missing", litres=1)


def test_tui_prefill_rejection_save_cancel(session):
    import asyncio

    from textual.widgets import Input, Static

    from odometer.tui.app import OdometerTUI
    from odometer.tui.screens.expenses import AddExpenseModal
    from odometer.tui.screens.fuel import AddFuelModal

    vehicle, service, rows = history(session)
    row = rows[1]
    identifier = row.id
    expense = ExpenseService(session).add_expense(
        vehicle_identifier=vehicle.id,
        date_=date(2026, 1, 1),
        category="SERVICE",
        amount_pence=1234,
        vendor="Garage",
        notes="original",
    )

    async def exercise():
        app = OdometerTUI()
        async with app.run_test(size=(100, 45)) as pilot:
            app.push_screen(AddFuelModal(row))
            await pilot.pause()
            assert app.screen.query_one("#vehicle", Input).disabled
            assert app.screen.query_one("#amount", Input).value == "30.00"
            app.screen.query_one("#mileage", Input).value = "999"
            await pilot.click("#save")
            await pilot.pause()
            assert isinstance(app.screen, AddFuelModal)
            assert app.screen.query_one("#mileage", Input).value == "999"
            assert "lower" in str(app.screen.query_one("#message", Static).render())
            app.screen.query_one("#mileage", Input).value = "210"
            app.screen.query_one("#amount", Input).value = "12.34"
            await pilot.pause(0.3)
            await pilot.click("#save")
            await pilot.pause()
            assert not isinstance(app.screen, AddFuelModal), str(
                app.screen.query_one("#message", Static).render()
            )
            app.push_screen(AddExpenseModal(expense))
            await pilot.pause()
            assert app.screen.query_one("#vendor", Input).value == "Garage"
            app.screen.query_one("#amount", Input).value = "99.99"
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, AddExpenseModal)

    asyncio.run(exercise())
    session.expire_all()
    assert service.repository.get_by_id(identifier).total_cost_pence == 1234
    assert expense.amount_pence == 1234


def test_date_id_order_and_equal_mileage(session):
    vehicle, service, rows = history(session)
    first = rows[0].model_copy(update={"id": "a", "odometer_miles": 100})
    second = rows[0].model_copy(update={"id": "b", "odometer_miles": 100})
    service.validate_candidate_history(vehicle, [second, first])
    second.odometer_miles = 99
    with pytest.raises(InvalidFuelLogError):
        service.validate_candidate_history(vehicle, [second, first])
    # A same-day successor with a lower reading is rejected in date/ID order.
    first.odometer_miles = 200
    second.odometer_miles = 150
    with pytest.raises(InvalidFuelLogError):
        service.validate_candidate_history(vehicle, [second, first])


def test_valid_older_corrections_and_derived_totals(session):
    from odometer.services.calculation_service import CalculationService
    from odometer.services.exceptions import CalculationUnavailableError

    vehicle, service, rows = history(session)
    calculations = CalculationService(session)
    before = calculations.mpg_stats(vehicle.id)
    service.update_fuel_log(rows[0].id, date_=date(2025, 12, 31))
    service.update_fuel_log(rows[1].id, date_=date(2026, 1, 1), litres=10)
    after = calculations.mpg_stats(vehicle.id)
    assert before is not None and after is not None
    assert after.average_mpg > before.average_mpg
    service.update_fuel_log(rows[2].id, is_full_tank=False)
    with pytest.raises(CalculationUnavailableError):
        calculations.mpg_stats(vehicle.id)


def test_persisted_legacy_tie_allows_unrelated_corrections(session):
    vehicle = VehicleService(session).create_vehicle(
        registration="LEGACY", initial_mileage=0, fuel_tank_litres=60
    )
    service = FuelService(session)
    for identifier, day, miles in [("z", 1, 100), ("a", 1, 200), ("later", 2, 300)]:
        service.repository.add(
            FuelLog(
                id=identifier,
                vehicle_id=vehicle.id,
                date=date(2026, 1, day),
                odometer_miles=miles,
                litres=20,
                total_cost_pence=3000,
            )
        )
    session.expire_all()
    service.update_fuel_log("z", notes="corrected", date_=date(2026, 1, 1), odometer_miles=100)
    service.update_fuel_log("later", total_cost_pence=1234)
    session.expire_all()
    assert session.get(FuelLog, "z").notes == "corrected"
    assert session.get(FuelLog, "later").total_cost_pence == 1234
    before = session.get(FuelLog, "z").model_dump()
    with pytest.raises(InvalidFuelLogError):
        service.update_fuel_log("z", odometer_miles=150)
    session.expire_all()
    assert session.get(FuelLog, "z").model_dump() == before
    with pytest.raises(InvalidFuelLogError):
        service.update_fuel_log("later", odometer_miles=50)
    # Imports still reject conflicts without an explicit persisted baseline.
    with pytest.raises(InvalidFuelLogError):
        service.validate_candidate_history(
            vehicle, service.repository.list(vehicle_id=vehicle.id, limit=None)
        )
    # A chronology correction that resolves the legacy conflict is allowed.
    service.update_fuel_log("z", odometer_miles=250)
    service.validate_candidate_history(
        vehicle, service.repository.list(vehicle_id=vehicle.id, limit=None)
    )


@pytest.mark.parametrize("category", [None, "", "   ", 42])
def test_invalid_expense_category_is_actionable_and_atomic(session, category):
    vehicle, _, _ = history(session)
    service = ExpenseService(session)
    row = service.add_expense(
        vehicle_identifier=vehicle.id, category="SERVICE", amount_pence=100, date_=date(2026, 1, 1)
    )
    before = row.model_dump()
    with pytest.raises(InvalidExpenseError, match="category is required"):
        service.update_expense(row.id, category=category)
    session.expire_all()
    session.refresh(row)
    assert row.model_dump() == before
    result = CliRunner().invoke(app, ["expense", "edit", row.id, "--category", ""])
    assert result.exit_code != 0
    assert "category is required" in result.output
    assert isinstance(result.exception, SystemExit)
    session.expire_all()
    session.refresh(row)
    assert row.model_dump() == before
