"""Vehicle detail screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from odometer.cli.helpers import format_mpg, format_pence_per_mile
from odometer.tui.app import OdometerTUI, VehicleDetailData
from odometer.tui.widgets.metric_card import MetricCard
from odometer.utils.formatting import format_optional_float, format_optional_int
from odometer.utils.money import format_money


class VehicleDetailScreen(Screen[None]):
    """Vehicle detail screen."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, vehicle_id: str) -> None:
        super().__init__()
        self.vehicle_id = vehicle_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("", id="title", classes="section")
            with Container(classes="metrics"):
                yield MetricCard("Total spend", "-", id="total-spend")
                yield MetricCard("Cost/mile", "-", id="cost-mile")
                yield MetricCard("Ownership/mile", "-", id="ownership-mile")
                yield MetricCard("Latest MPG", "-", id="latest-mpg")
            yield Static("[b]Latest expenses[/b]", classes="section")
            yield DataTable(id="expenses-table")
            yield Static("[b]Latest fuel logs[/b]", classes="section")
            yield DataTable(id="fuel-table")
        yield Footer()

    def on_mount(self) -> None:
        """Load vehicle data."""
        self.refresh_screen()

    def action_refresh(self) -> None:
        """Refresh the screen."""
        self.refresh_screen()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
            self.refresh_screen()

    def action_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()

    def refresh_screen(self) -> None:
        """Refresh vehicle detail data."""
        app = cast(OdometerTUI, self.app)
        data = app.get_vehicle_detail(self.vehicle_id)
        vehicle = data.vehicle
        tank = format_optional_float(vehicle.fuel_tank_litres, suffix=" L", precision=1)
        self.query_one("#title", Static).update(
            f"[b]{vehicle.registration}[/b] {vehicle.make or ''} {vehicle.model or ''} Tank {tank}"
        )
        self.query_one("#total-spend", MetricCard).update(
            f"[b]Total spend[/b]\n{format_money(data.metrics.running_cost_pence)}"
        )
        self.query_one("#cost-mile", MetricCard).update(
            f"[b]Cost/mile[/b]\n{format_pence_per_mile(data.metrics.running_cost_per_mile_pence)}"
        )
        self.query_one("#ownership-mile", MetricCard).update(
            "[b]Ownership/mile[/b]\n"
            f"{format_pence_per_mile(data.metrics.ownership_cost_per_mile_pence)}"
        )
        latest_mpg = data.mpg_stats.latest_mpg if data.mpg_stats else None
        self.query_one("#latest-mpg", MetricCard).update(
            f"[b]Latest MPG[/b]\n{format_mpg(latest_mpg)}"
        )
        self._refresh_expenses(data)
        self._refresh_fuel(data)

    def _refresh_expenses(self, data: VehicleDetailData) -> None:
        detail = data
        table = self.query_one("#expenses-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Category", "Amount", "Mileage", "Description")
        for expense in detail.latest_expenses:
            table.add_row(
                expense.date.isoformat(),
                expense.category.value,
                format_money(expense.amount_pence),
                format_optional_int(expense.odometer_miles),
                expense.description or "-",
            )

    def _refresh_fuel(self, data: VehicleDetailData) -> None:
        detail = data
        table = self.query_one("#fuel-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Mileage", "Litres", "Amount", "Fill", "Station")
        for fuel_log in detail.latest_fuel_logs:
            table.add_row(
                fuel_log.date.isoformat(),
                f"{fuel_log.odometer_miles:,}",
                f"{fuel_log.litres:.2f}",
                format_money(fuel_log.total_cost_pence),
                "Full" if fuel_log.is_full_tank else "Partial",
                fuel_log.station or "-",
            )
