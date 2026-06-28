"""Textual application for Odometer."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TypeVar

from sqlmodel import Session
from textual.app import App

from odometer.db.bootstrap import initialise_database
from odometer.db.session import get_database_path, get_session
from odometer.models.expense import Expense
from odometer.models.fuel import FuelLog
from odometer.models.vehicle import Vehicle
from odometer.services.calculation_service import (
    CalculationService,
    CategoryBreakdownItem,
    MPGStats,
    PeriodSummary,
    VehicleCostMetrics,
)
from odometer.services.exceptions import CalculationUnavailableError
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.summary_service import OverallSummary, SummaryService
from odometer.services.vehicle_service import VehicleService
from odometer.utils.dates import parse_optional_date
from odometer.utils.money import parse_money_to_pence

T = TypeVar("T")


@dataclass(frozen=True)
class DashboardData:
    """Data needed by the dashboard screen."""

    database_path: str
    active_vehicle_count: int
    summary: OverallSummary
    average_running_cost_per_mile_pence: float | None
    latest_mpg: float | None
    monthly_spend: list[tuple[str, int]]


@dataclass(frozen=True)
class VehicleOverviewRow:
    """A row for the vehicles screen."""

    metrics: VehicleCostMetrics


@dataclass(frozen=True)
class VehicleDetailData:
    """Data needed by the vehicle detail screen."""

    vehicle: Vehicle
    metrics: VehicleCostMetrics
    latest_expenses: list[Expense]
    latest_fuel_logs: list[FuelLog]
    mpg_stats: MPGStats | None


@dataclass(frozen=True)
class ExpenseTableRow:
    """A row for the expenses screen."""

    expense: Expense
    registration: str


@dataclass(frozen=True)
class FuelTableRow:
    """A row for the fuel screen."""

    fuel_log: FuelLog
    registration: str


@dataclass(frozen=True)
class SummariesData:
    """Data needed by the summaries screen."""

    categories: list[CategoryBreakdownItem]
    monthly: list[PeriodSummary]
    annual: list[PeriodSummary]


class OdometerTUI(App[None]):
    """Odometer Textual application."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #content {
        padding: 1 2;
        height: 1fr;
    }

    .metrics {
        layout: grid;
        grid-size: 4;
        grid-gutter: 1 2;
        height: auto;
        margin-bottom: 1;
    }

    .metric-card {
        border: solid $primary;
        padding: 1;
        height: 6;
    }

    .section {
        margin-top: 1;
        margin-bottom: 1;
    }

    DataTable {
        height: 1fr;
    }

    Input {
        margin-bottom: 1;
    }

    #message {
        color: $error;
        height: auto;
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("d", "show_dashboard", "Dashboard"),
        ("v", "show_vehicles", "Vehicles"),
        ("e", "show_expenses", "Expenses"),
        ("f", "show_fuel", "Fuel"),
        ("s", "show_summaries", "Summaries"),
        ("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        """Show the dashboard on startup."""
        self._install_screens()
        self.push_screen("dashboard")

    def get_dashboard_data(self) -> DashboardData:
        """Return dashboard data."""

        def load(session: Session) -> DashboardData:
            vehicle_service = VehicleService(session)
            summary_service = SummaryService(session)
            calculation_service = CalculationService(session)
            vehicles = vehicle_service.list_vehicles()
            summary = summary_service.overall_summary()
            metrics = calculation_service.vehicle_cost_metrics()
            total_miles = sum(row.miles_driven for row in metrics)
            total_cost = sum(row.running_cost_pence for row in metrics)
            average_cpm = (
                calculation_service.cost_per_mile_pence(total_cost, total_miles)
                if total_miles > 0
                else None
            )
            latest_mpg = self._latest_available_mpg(calculation_service, vehicles)
            monthly = summary_service.monthly_summary(year=date.today().year)
            monthly_spend = [
                (row.period[5:], row.total_spend_pence)
                for row in monthly
                if row.total_spend_pence > 0
            ][-6:]
            return DashboardData(
                database_path=str(get_database_path()),
                active_vehicle_count=len(vehicles),
                summary=summary,
                average_running_cost_per_mile_pence=average_cpm,
                latest_mpg=latest_mpg,
                monthly_spend=monthly_spend,
            )

        return self._with_session(load)

    def get_vehicle_rows(self) -> list[VehicleOverviewRow]:
        """Return vehicle overview rows."""

        def load(session: Session) -> list[VehicleOverviewRow]:
            calculations = CalculationService(session)
            return [VehicleOverviewRow(metrics=row) for row in calculations.vehicle_cost_metrics()]

        return self._with_session(load)

    def get_vehicle_detail(self, vehicle_id: str) -> VehicleDetailData:
        """Return vehicle detail data."""

        def load(session: Session) -> VehicleDetailData:
            vehicle = VehicleService(session).get_vehicle(vehicle_id)
            calculations = CalculationService(session)
            metrics = calculations.vehicle_cost_metrics(vehicle.id)[0]
            latest_expenses = ExpenseService(session).list_expenses(
                vehicle_identifier=vehicle.id,
                limit=10,
            )
            latest_fuel_logs = FuelService(session).list_fuel_logs(
                vehicle_identifier=vehicle.id,
                limit=10,
            )
            try:
                mpg_stats = calculations.mpg_stats(vehicle.id)
            except CalculationUnavailableError:
                mpg_stats = None
            return VehicleDetailData(
                vehicle=vehicle,
                metrics=metrics,
                latest_expenses=latest_expenses,
                latest_fuel_logs=latest_fuel_logs,
                mpg_stats=mpg_stats,
            )

        return self._with_session(load)

    def get_expenses(self) -> list[ExpenseTableRow]:
        """Return latest expenses."""

        def load(session: Session) -> list[ExpenseTableRow]:
            vehicle_service = VehicleService(session)
            expenses = ExpenseService(session).list_expenses(limit=200)
            return [
                ExpenseTableRow(
                    expense=expense,
                    registration=vehicle_service.get_vehicle(expense.vehicle_id).registration,
                )
                for expense in expenses
            ]

        return self._with_session(load)

    def get_fuel_logs(self) -> list[FuelTableRow]:
        """Return latest fuel logs."""

        def load(session: Session) -> list[FuelTableRow]:
            vehicle_service = VehicleService(session)
            fuel_logs = FuelService(session).list_fuel_logs(limit=200)
            return [
                FuelTableRow(
                    fuel_log=fuel_log,
                    registration=vehicle_service.get_vehicle(fuel_log.vehicle_id).registration,
                )
                for fuel_log in fuel_logs
            ]

        return self._with_session(load)

    def get_summaries_data(self) -> SummariesData:
        """Return summary screen data."""

        def load(session: Session) -> SummariesData:
            service = SummaryService(session)
            return SummariesData(
                categories=service.category_breakdown(),
                monthly=service.monthly_summary(year=date.today().year),
                annual=service.annual_summary(),
            )

        return self._with_session(load)

    def add_vehicle_from_form(self, values: dict[str, str]) -> None:
        """Add a vehicle from TUI form values."""

        def save(session: Session) -> None:
            VehicleService(session).create_vehicle(
                registration=values["registration"],
                make=values.get("make") or None,
                model=values.get("model") or None,
                nickname=values.get("nickname") or None,
                year=int(values["year"]) if values.get("year") else None,
                initial_mileage=int(values["initial_mileage"]),
                fuel_tank_litres=(
                    float(values["fuel_tank_litres"]) if values.get("fuel_tank_litres") else None
                ),
                purchase_date=parse_optional_date(values.get("purchase_date") or None),
                purchase_price_pence=(
                    parse_money_to_pence(values["purchase_price"])
                    if values.get("purchase_price")
                    else None
                ),
            )

        self._with_session(save)

    def add_expense_from_form(self, values: dict[str, str]) -> None:
        """Add an expense from TUI form values."""

        def save(session: Session) -> None:
            ExpenseService(session).add_expense(
                vehicle_identifier=values["vehicle"],
                category=values["category"],
                amount_pence=parse_money_to_pence(values["amount"]),
                date_=parse_optional_date(values.get("date") or None) or date.today(),
                odometer_miles=int(values["mileage"]) if values.get("mileage") else None,
                description=values.get("description") or None,
            )

        self._with_session(save)

    def add_fuel_from_form(self, values: dict[str, str]) -> None:
        """Add a fuel log from TUI form values."""

        def save(session: Session) -> None:
            FuelService(session).add_fuel_log(
                vehicle_identifier=values["vehicle"],
                litres=float(values["litres"]),
                total_cost_pence=parse_money_to_pence(values["amount"]),
                odometer_miles=int(values["mileage"]),
                date_=parse_optional_date(values.get("date") or None) or date.today(),
                station=values.get("station") or None,
                is_full_tank=values.get("fill", "full").lower() != "partial",
            )

        self._with_session(save)

    def action_show_dashboard(self) -> None:
        """Navigate to dashboard."""
        self.switch_screen("dashboard")

    def action_show_vehicles(self) -> None:
        """Navigate to vehicles."""
        self.switch_screen("vehicles")

    def action_show_expenses(self) -> None:
        """Navigate to expenses."""
        self.switch_screen("expenses")

    def action_show_fuel(self) -> None:
        """Navigate to fuel."""
        self.switch_screen("fuel")

    def action_show_summaries(self) -> None:
        """Navigate to summaries."""
        self.switch_screen("summaries")

    def _install_screens(self) -> None:
        """Register screens."""
        from odometer.tui.screens.dashboard import DashboardScreen
        from odometer.tui.screens.expenses import ExpensesScreen
        from odometer.tui.screens.fuel import FuelScreen
        from odometer.tui.screens.summaries import SummariesScreen
        from odometer.tui.screens.vehicles import VehiclesScreen

        self.install_screen(DashboardScreen(), name="dashboard")
        self.install_screen(VehiclesScreen(), name="vehicles")
        self.install_screen(ExpensesScreen(), name="expenses")
        self.install_screen(FuelScreen(), name="fuel")
        self.install_screen(SummariesScreen(), name="summaries")

    def _with_session(self, callback: Callable[[Session], T]) -> T:
        initialise_database()
        with get_session() as session:
            return callback(session)

    @staticmethod
    def _latest_available_mpg(
        calculation_service: CalculationService, vehicles: list[Vehicle]
    ) -> float | None:
        for vehicle in vehicles:
            try:
                return calculation_service.mpg_stats(vehicle.id).latest_mpg
            except CalculationUnavailableError:
                continue
        return None
