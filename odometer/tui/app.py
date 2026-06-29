"""Textual application for Odometer."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TypeVar

from sqlmodel import Session
from textual.app import App

from odometer.db.bootstrap import initialise_database
from odometer.db.session import get_database_path, get_session
from odometer.models.enums import VehicleStatus
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
from odometer.services.vehicle_service import VehicleDeletionResult, VehicleService
from odometer.utils.dates import parse_optional_date
from odometer.utils.money import parse_money_to_pence

T = TypeVar("T")

VEHICLE_CONTEXT_ALL = "__all__"
VEHICLE_CONTEXT_ALL_LABEL = "All vehicles"


@dataclass(frozen=True)
class DashboardData:
    """Data needed by the dashboard screen."""

    database_path: str
    vehicle_count: int
    vehicle_context_label: str
    summary: OverallSummary
    average_running_cost_per_mile_pence: float | None
    latest_mpg: float | None
    monthly_spend: list[tuple[str, int]]
    monthly_mileage: list[tuple[str, int]]


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

    vehicle_label: str
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

    .charts {
        layout: grid;
        grid-size: 2;
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

    Select {
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

    def __init__(self) -> None:
        """Initialise app-level state shared by all TUI screens."""
        super().__init__()
        self.selected_vehicle_id: str | None = None

    @property
    def vehicle_context_value(self) -> str:
        """Return the select value for the current vehicle context."""
        return self.selected_vehicle_id or VEHICLE_CONTEXT_ALL

    def set_vehicle_context(self, value: str) -> None:
        """Set the current vehicle context from a select value."""
        self.selected_vehicle_id = None if value == VEHICLE_CONTEXT_ALL else value

    def get_vehicle_context_options(self) -> list[tuple[str, str]]:
        """Return vehicle context options for screens with scoped data."""

        def load(session: Session) -> list[tuple[str, str]]:
            """Load all vehicles and convert them to select options."""
            vehicles = VehicleService(session).list_vehicles(include_inactive=True)
            return [(VEHICLE_CONTEXT_ALL_LABEL, VEHICLE_CONTEXT_ALL)] + [
                (self._vehicle_context_label(vehicle), vehicle.id) for vehicle in vehicles
            ]

        return self._with_session(load)

    def should_show_vehicle_context_select(self) -> bool:
        """Return whether scoped screens need a visible vehicle context selector."""

        def load(session: Session) -> bool:
            """Check the fleet size that determines selector visibility."""
            vehicles = VehicleService(session).list_vehicles(include_inactive=True)
            return len(vehicles) != 1

        return self._with_session(load)

    def on_mount(self) -> None:
        """Show the dashboard on startup."""
        self._install_screens()
        self.push_screen("dashboard")

    def get_dashboard_data(self) -> DashboardData:
        """Return dashboard data."""

        def load(session: Session) -> DashboardData:
            """Load and aggregate the current dashboard context."""
            vehicle_service = VehicleService(session)
            summary_service = SummaryService(session)
            calculation_service = CalculationService(session)
            context_vehicles = vehicle_service.list_vehicles(include_inactive=True)
            selected_vehicle_id = self._effective_vehicle_context_id(context_vehicles)
            include_inactive = selected_vehicle_id is None
            vehicles = self._vehicles_for_context(
                vehicle_service,
                selected_vehicle_id=selected_vehicle_id,
                context_vehicles=context_vehicles,
            )
            summary = summary_service.overall_summary(
                vehicle_identifier=selected_vehicle_id,
                include_inactive=include_inactive,
            )
            metrics = calculation_service.vehicle_cost_metrics(
                selected_vehicle_id,
                include_inactive=include_inactive,
            )
            total_miles = sum(row.miles_driven for row in metrics)
            total_cost = sum(row.running_cost_pence for row in metrics)
            average_cpm = (
                calculation_service.cost_per_mile_pence(total_cost, total_miles)
                if total_miles > 0
                else None
            )
            latest_mpg = self._latest_available_mpg(calculation_service, vehicles)
            monthly = summary_service.monthly_summary(
                vehicle_identifier=selected_vehicle_id,
                year=date.today().year,
                include_inactive=include_inactive,
            )
            monthly_spend = [
                (row.period[5:], row.total_spend_pence)
                for row in monthly
                if row.total_spend_pence > 0
            ][-6:]
            monthly_mileage = [
                (row.period[5:], row.miles_driven)
                for row in monthly
                if row.miles_driven is not None and row.miles_driven > 0
            ][-6:]
            return DashboardData(
                database_path=str(get_database_path()),
                vehicle_count=len(vehicles),
                vehicle_context_label=self._context_label_for_vehicles(
                    vehicles,
                    selected_vehicle_id,
                ),
                summary=summary,
                average_running_cost_per_mile_pence=average_cpm,
                latest_mpg=latest_mpg,
                monthly_spend=monthly_spend,
                monthly_mileage=monthly_mileage,
            )

        return self._with_session(load)

    def get_vehicle_rows(self) -> list[VehicleOverviewRow]:
        """Return vehicle overview rows."""

        def load(session: Session) -> list[VehicleOverviewRow]:
            """Load cost metrics for the vehicle overview table."""
            calculations = CalculationService(session)
            return [VehicleOverviewRow(metrics=row) for row in calculations.vehicle_cost_metrics()]

        return self._with_session(load)

    def get_vehicle_detail(self, vehicle_id: str) -> VehicleDetailData:
        """Return vehicle detail data."""

        def load(session: Session) -> VehicleDetailData:
            """Load one vehicle plus its latest costs, expenses, fuel, and MPG."""
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
            """Load visible expenses and attach display registrations."""
            vehicle_service = VehicleService(session)
            selected_vehicle_id = self._effective_vehicle_context_id(
                vehicle_service.list_vehicles(include_inactive=True)
            )
            expenses = ExpenseService(session).list_expenses(
                vehicle_identifier=selected_vehicle_id,
                limit=200,
            )
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
            """Load visible fuel logs and attach display registrations."""
            vehicle_service = VehicleService(session)
            selected_vehicle_id = self._effective_vehicle_context_id(
                vehicle_service.list_vehicles(include_inactive=True)
            )
            fuel_logs = FuelService(session).list_fuel_logs(
                vehicle_identifier=selected_vehicle_id,
                limit=200,
            )
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
            """Load category, monthly, and annual summaries for the context."""
            service = SummaryService(session)
            vehicle_service = VehicleService(session)
            selected_vehicle_id = self._effective_vehicle_context_id(
                vehicle_service.list_vehicles(include_inactive=True)
            )
            include_inactive = selected_vehicle_id is None
            vehicle_label = VEHICLE_CONTEXT_ALL_LABEL
            if selected_vehicle_id is not None:
                vehicle_label = vehicle_service.get_vehicle(selected_vehicle_id).registration
            return SummariesData(
                vehicle_label=vehicle_label,
                categories=service.category_breakdown(
                    vehicle_identifier=selected_vehicle_id,
                    include_inactive=include_inactive,
                ),
                monthly=service.monthly_summary(
                    vehicle_identifier=selected_vehicle_id,
                    year=date.today().year,
                    include_inactive=include_inactive,
                ),
                annual=service.annual_summary(
                    vehicle_identifier=selected_vehicle_id,
                    include_inactive=include_inactive,
                ),
            )

        return self._with_session(load)

    def add_vehicle_from_form(self, values: dict[str, str]) -> None:
        """Add a vehicle from TUI form values."""

        def save(session: Session) -> None:
            """Parse form fields and persist a new vehicle."""
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
            """Parse form fields and persist a new expense."""
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
            """Parse form fields and persist a new fuel log."""
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

    def delete_vehicle(self, vehicle_id: str) -> VehicleDeletionResult:
        """Delete a vehicle and associated data from the TUI."""

        def delete(session: Session) -> VehicleDeletionResult:
            """Delete one vehicle and return the cascade summary."""
            return VehicleService(session).delete_vehicle(vehicle_id)

        result = self._with_session(delete)
        if self.selected_vehicle_id == result.vehicle_id:
            self.selected_vehicle_id = None
        return result

    def delete_expense(self, expense_id: str) -> None:
        """Delete an expense from the TUI."""

        def delete(session: Session) -> None:
            """Delete one expense by id."""
            ExpenseService(session).delete_expense(expense_id)

        self._with_session(delete)

    def delete_fuel_log(self, fuel_log_id: str) -> None:
        """Delete a fuel log from the TUI."""

        def delete(session: Session) -> None:
            """Delete one fuel log by id."""
            FuelService(session).delete_fuel_log(fuel_log_id)

        self._with_session(delete)

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
        """Run a TUI data operation inside a fresh database session."""
        initialise_database()
        with get_session() as session:
            return callback(session)

    def _vehicles_for_context(
        self,
        vehicle_service: VehicleService,
        *,
        selected_vehicle_id: str | None,
        context_vehicles: list[Vehicle],
    ) -> list[Vehicle]:
        """Return the vehicle set represented by the effective TUI context."""
        if selected_vehicle_id is not None:
            return [vehicle_service.get_vehicle(selected_vehicle_id)]
        return context_vehicles

    def _effective_vehicle_context_id(self, vehicles: list[Vehicle]) -> str | None:
        """Return the selected vehicle or the only vehicle in a single-vehicle database."""
        if self.selected_vehicle_id is not None and any(
            vehicle.id == self.selected_vehicle_id for vehicle in vehicles
        ):
            return self.selected_vehicle_id
        if len(vehicles) == 1:
            return vehicles[0].id
        return None

    def _context_label_for_vehicles(
        self,
        vehicles: list[Vehicle],
        selected_vehicle_id: str | None,
    ) -> str:
        """Return a human-readable label for the current TUI context."""
        if selected_vehicle_id is None and len(vehicles) != 1:
            return VEHICLE_CONTEXT_ALL_LABEL
        return self._vehicle_context_label(vehicles[0]) if vehicles else VEHICLE_CONTEXT_ALL_LABEL

    @staticmethod
    def _vehicle_context_label(vehicle: Vehicle) -> str:
        """Return the selector label for one vehicle."""
        make_model = " ".join(part for part in [vehicle.make, vehicle.model] if part)
        detail = vehicle.nickname or make_model
        label = vehicle.registration
        if detail:
            label = f"{label} ({detail})"
        if vehicle.status is not VehicleStatus.ACTIVE:
            label = f"{label} - {vehicle.status.value}"
        return label

    @staticmethod
    def _latest_available_mpg(
        calculation_service: CalculationService, vehicles: list[Vehicle]
    ) -> float | None:
        """Return the first latest MPG value available for the current context."""
        for vehicle in vehicles:
            try:
                return calculation_service.mpg_stats(vehicle.id).latest_mpg
            except CalculationUnavailableError:
                continue
        return None
