"""TUI screen tests."""

import asyncio
from datetime import date

from sqlmodel import Session
from textual.widgets import Button, DataTable, Select, Static

from odometer.models.enums import ExpenseCategory
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService
from odometer.tui.app import VEHICLE_CONTEXT_ALL, OdometerTUI
from odometer.tui.screens.expenses import expense_category_options
from odometer.tui.screens.tables import fitted_column_widths
from odometer.tui.widgets.simple_bar_chart import SimpleBarChart


def test_expense_category_options_exclude_fuel() -> None:
    """Verify the TUI expense form offers non-fuel expense categories only."""
    options = expense_category_options()
    values = [value for _, value in options]

    assert ExpenseCategory.FUEL.value not in values
    assert set(values) == {
        category.value for category in ExpenseCategory if category is not ExpenseCategory.FUEL
    }
    assert ("Fine", ExpenseCategory.FINE.value) in options
    assert (ExpenseCategory.MOT.value, ExpenseCategory.MOT.value) in options


def test_fitted_column_widths_fit_headers_and_cells() -> None:
    """Verify table column width calculation fits headers and loaded cell data."""
    widths = fitted_column_widths(
        ("Registration", "Amount"),
        (
            ("AB12 CDE", "GBP 1.00"),
            ("LONG REGISTRATION", "GBP 1,234.56"),
        ),
    )

    assert widths == [len("LONG REGISTRATION"), len("GBP 1,234.56")]


def test_tui_vehicle_context_filters_scoped_data(session: Session) -> None:
    """Verify app-level TUI data methods respect selected vehicle context."""
    vehicle_service = VehicleService(session)
    first = vehicle_service.create_vehicle(
        registration="AB12 CDE",
        initial_mileage=10_000,
        fuel_tank_litres=50,
    )
    second = vehicle_service.create_vehicle(
        registration="XY98 ZZZ",
        initial_mileage=20_000,
        fuel_tank_litres=60,
    )
    expenses = ExpenseService(session)
    fuel = FuelService(session)

    expenses.add_expense(
        vehicle_identifier=first.id,
        category="service",
        amount_pence=1_000,
        date_=date(2026, 1, 1),
        odometer_miles=10_100,
    )
    fuel.add_fuel_log(
        vehicle_identifier=first.id,
        litres=10,
        total_cost_pence=2_000,
        odometer_miles=10_200,
        date_=date(2026, 1, 2),
    )
    expenses.add_expense(
        vehicle_identifier=second.id,
        category="repair",
        amount_pence=3_000,
        date_=date(2026, 1, 3),
        odometer_miles=20_100,
    )
    fuel.add_fuel_log(
        vehicle_identifier=second.id,
        litres=20,
        total_cost_pence=4_000,
        odometer_miles=20_200,
        date_=date(2026, 1, 4),
    )
    vehicle_service.mark_vehicle_sold(second.id)

    app = OdometerTUI()
    options = app.get_vehicle_context_options()
    assert {value for _label, value in options} >= {VEHICLE_CONTEXT_ALL, first.id, second.id}

    app.set_vehicle_context(first.id)
    dashboard = app.get_dashboard_data()
    summaries = app.get_summaries_data()
    assert dashboard.vehicle_count == 1
    assert dashboard.summary.total_spend_pence == 3_000
    assert dashboard.monthly_mileage == [("01", 200)]
    assert sum(row.amount_pence for row in summaries.categories) == 3_000
    assert {row.expense.vehicle_id for row in app.get_expenses()} == {first.id}
    assert {row.fuel_log.vehicle_id for row in app.get_fuel_logs()} == {first.id}

    app.set_vehicle_context(VEHICLE_CONTEXT_ALL)
    dashboard = app.get_dashboard_data()
    summaries = app.get_summaries_data()
    assert dashboard.vehicle_count == 2
    assert dashboard.summary.total_spend_pence == 10_000
    assert dashboard.monthly_mileage == [("01", 400)]
    assert sum(row.amount_pence for row in summaries.categories) == 10_000
    assert {row.expense.vehicle_id for row in app.get_expenses()} == {first.id, second.id}
    assert {row.fuel_log.vehicle_id for row in app.get_fuel_logs()} == {first.id, second.id}


def test_tui_single_vehicle_context_is_implicit(session: Session) -> None:
    """Verify one-vehicle databases hide context controls and scope to that vehicle."""
    vehicle_service = VehicleService(session)
    vehicle = vehicle_service.create_vehicle(
        registration="AB12 CDE",
        initial_mileage=10_000,
        fuel_tank_litres=50,
    )
    ExpenseService(session).add_expense(
        vehicle_identifier=vehicle.id,
        category="service",
        amount_pence=1_000,
        date_=date(2026, 1, 1),
        odometer_miles=10_100,
    )
    FuelService(session).add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=10,
        total_cost_pence=2_000,
        odometer_miles=10_200,
        date_=date(2026, 1, 2),
    )

    app = OdometerTUI()
    assert app.should_show_vehicle_context_select() is False
    assert app.vehicle_context_value == VEHICLE_CONTEXT_ALL

    dashboard = app.get_dashboard_data()
    summaries = app.get_summaries_data()
    assert dashboard.vehicle_count == 1
    assert dashboard.vehicle_context_label == "AB12 CDE"
    assert dashboard.summary.total_spend_pence == 3_000
    assert dashboard.monthly_mileage == [("01", 200)]
    assert summaries.vehicle_label == "AB12 CDE"
    assert sum(row.amount_pence for row in summaries.categories) == 3_000
    assert {row.expense.vehicle_id for row in app.get_expenses()} == {vehicle.id}
    assert {row.fuel_log.vehicle_id for row in app.get_fuel_logs()} == {vehicle.id}

    async def run() -> None:
        """Verify scoped screens hide the context selector when rendered."""
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            assert app.screen.query_one("#vehicle-context", Select).display is False

            await pilot.press("e")
            await pilot.pause()
            assert app.screen.query_one("#vehicle-context", Select).display is False

            await pilot.press("f")
            await pilot.pause()
            assert app.screen.query_one("#vehicle-context", Select).display is False

            await pilot.press("s")
            await pilot.pause()
            assert app.screen.query_one("#vehicle-context", Select).display is False

    asyncio.run(run())


def test_tui_screens_render_tables_charts_and_context(session: Session) -> None:
    """Verify key TUI screens render scoped tables and monthly mileage charts."""
    data = _seed_tui_data(session)

    async def run() -> None:
        """Drive the Textual app through dashboard, tables, and summaries."""
        app = OdometerTUI()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            dashboard = app.screen
            mileage_chart = dashboard.query_one("#monthly-mileage", SimpleBarChart)
            assert "Monthly mileage" in str(mileage_chart.content)
            assert "450 mi" in str(mileage_chart.content)

            select = dashboard.query_one("#vehicle-context", Select)
            select.value = data["first_id"]
            await pilot.pause()
            context = dashboard.query_one("#database-path", Static)
            assert "AB12 CDE" in str(context.content)
            assert "250 mi" in str(mileage_chart.content)

            await pilot.press("v")
            await pilot.pause()
            vehicles_table = app.screen.query_one("#vehicles-table", DataTable)
            assert vehicles_table.row_count == 2
            assert vehicles_table.get_row_at(0)[0] == "AB12 CDE"

            app.screen.action_open_selected()
            await pilot.pause()
            detail_expenses = app.screen.query_one("#expenses-table", DataTable)
            detail_fuel = app.screen.query_one("#fuel-table", DataTable)
            assert detail_expenses.get_row_at(0)[0] == "AB12 CDE"
            assert detail_fuel.get_row_at(0)[0] == "AB12 CDE"

            await pilot.press("escape")
            await pilot.press("e")
            await pilot.pause()
            expenses_table = app.screen.query_one("#expenses-table", DataTable)
            assert expenses_table.row_count == 1
            assert expenses_table.get_row_at(0)[1] == "AB12 CDE"

            await pilot.press("f")
            await pilot.pause()
            fuel_table = app.screen.query_one("#fuel-table", DataTable)
            assert fuel_table.row_count == 2
            assert fuel_table.get_row_at(0)[1] == "AB12 CDE"

            await pilot.press("s")
            await pilot.pause()
            summary_mileage = app.screen.query_one("#monthly-mileage-chart", SimpleBarChart)
            monthly_table = app.screen.query_one("#monthly-table", DataTable)
            assert "250 mi" in str(summary_mileage.content)
            assert monthly_table.get_row_at(0)[0] == "AB12 CDE"

    asyncio.run(run())


def test_tui_delete_actions_confirm_and_refresh_tables(session: Session) -> None:
    """Verify TUI delete confirmations remove rows and refresh visible tables."""
    data = _seed_tui_data(session)

    async def run() -> None:
        """Drive delete actions through expense, fuel, and vehicle screens."""
        app = OdometerTUI()
        app.set_vehicle_context(data["first_id"])
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            await pilot.press("e")
            await pilot.pause()
            await pilot.press("delete")
            await pilot.pause()
            app.screen.query_one("#delete", Button).action_press()
            await pilot.pause()
            expenses_table = app.screen.query_one("#expenses-table", DataTable)
            assert expenses_table.row_count == 0

            await pilot.press("f")
            await pilot.pause()
            await pilot.press("delete")
            await pilot.pause()
            app.screen.query_one("#delete", Button).action_press()
            await pilot.pause()
            fuel_table = app.screen.query_one("#fuel-table", DataTable)
            assert fuel_table.row_count == 1

            await pilot.press("v")
            await pilot.pause()
            await pilot.press("delete")
            await pilot.pause()
            app.screen.query_one("#delete", Button).action_press()
            await pilot.pause()
            vehicles_table = app.screen.query_one("#vehicles-table", DataTable)
            assert vehicles_table.row_count == 1
            assert vehicles_table.get_row_at(0)[0] == "XY98 ZZZ"

    asyncio.run(run())

    remaining_vehicle = VehicleService(session).list_vehicles(include_inactive=True)[0]
    assert remaining_vehicle.registration == "XY98 ZZZ"
    remaining_expenses = ExpenseService(session).list_expenses()
    assert len(remaining_expenses) == 1
    assert remaining_expenses[0].vehicle_id == data["second_id"]
    remaining_fuel = FuelService(session).list_fuel_logs()
    assert len(remaining_fuel) == 1
    assert remaining_fuel[0].vehicle_id == data["second_id"]


def test_tui_add_modals_show_validation_errors_and_cancel(session: Session) -> None:
    """Verify add modals surface validation errors and can be cancelled."""
    _seed_tui_data(session)

    async def run() -> None:
        """Open each add modal and exercise save validation plus cancel."""
        app = OdometerTUI()
        async with app.run_test(size=(160, 80)) as pilot:
            await pilot.pause()

            await pilot.press("v")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.click("#save")
            await pilot.pause()
            assert app.screen.query_one("#message", Static).content
            await pilot.click("#cancel")
            await pilot.pause()

            await pilot.press("e")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.click("#save")
            await pilot.pause()
            assert app.screen.query_one("#message", Static).content
            await pilot.click("#cancel")
            await pilot.pause()

            await pilot.press("f")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.click("#save")
            await pilot.pause()
            assert app.screen.query_one("#message", Static).content
            await pilot.click("#cancel")
            await pilot.pause()

    asyncio.run(run())


def _seed_tui_data(session: Session) -> dict[str, str]:
    """Create two vehicles plus expenses and fuel logs for TUI screen tests."""
    vehicle_service = VehicleService(session)
    first = vehicle_service.create_vehicle(
        registration="AB12 CDE",
        initial_mileage=10_000,
        fuel_tank_litres=50,
    )
    second = vehicle_service.create_vehicle(
        registration="XY98 ZZZ",
        initial_mileage=20_000,
        fuel_tank_litres=60,
    )
    expenses = ExpenseService(session)
    fuel = FuelService(session)
    expenses.add_expense(
        vehicle_identifier=first.id,
        category="service",
        amount_pence=1_000,
        date_=date(2026, 1, 1),
        odometer_miles=10_100,
        description="Annual service",
    )
    fuel.add_fuel_log(
        vehicle_identifier=first.id,
        litres=10,
        total_cost_pence=2_000,
        odometer_miles=10_250,
        date_=date(2026, 1, 2),
        station="Station One",
    )
    fuel.add_fuel_log(
        vehicle_identifier=first.id,
        litres=12,
        total_cost_pence=2_400,
        odometer_miles=10_400,
        date_=date(2026, 2, 2),
        station="Station Two",
    )
    expenses.add_expense(
        vehicle_identifier=second.id,
        category="repair",
        amount_pence=3_000,
        date_=date(2026, 1, 3),
        odometer_miles=20_100,
    )
    fuel.add_fuel_log(
        vehicle_identifier=second.id,
        litres=20,
        total_cost_pence=4_000,
        odometer_miles=20_200,
        date_=date(2026, 1, 4),
    )
    return {"first_id": first.id, "second_id": second.id}
