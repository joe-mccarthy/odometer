"""Dashboard screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Select, Static

from odometer.cli.helpers import format_mpg, format_pence_per_mile
from odometer.tui.app import OdometerTUI
from odometer.tui.screens.context import (
    handle_vehicle_context_changed,
    refresh_vehicle_context_select,
    vehicle_context_select,
)
from odometer.tui.widgets.metric_card import MetricCard
from odometer.tui.widgets.simple_bar_chart import SimpleBarChart
from odometer.utils.formatting import format_miles
from odometer.utils.money import format_money


class DashboardScreen(Screen[None]):
    """Interactive dashboard."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Build dashboard metrics, charts, and shared vehicle selector."""
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Odometer[/b]", classes="section")
            yield vehicle_context_select()
            yield Static("", id="database-path", classes="section")
            with Container(classes="metrics"):
                yield MetricCard("Vehicles", "-", id="vehicles")
                yield MetricCard("Total spend", "-", id="total-spend")
                yield MetricCard("Fuel spend", "-", id="fuel-spend")
                yield MetricCard("Avg cost/mi", "-", id="avg-cost-mile")
            with Container(classes="metrics"):
                yield MetricCard("Latest MPG", "-", id="latest-mpg")
                yield MetricCard("Expenses", "-", id="expenses")
                yield MetricCard("Fuel logs", "-", id="fuel-logs")
                yield MetricCard("Monthly avg", "-", id="monthly-avg")
            with Container(classes="charts"):
                yield SimpleBarChart("Monthly spend", [], id="monthly-spend")
                yield SimpleBarChart(
                    "Monthly mileage",
                    [],
                    value_formatter=format_miles,
                    id="monthly-mileage",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Populate dashboard data."""
        refresh_vehicle_context_select(self)
        self.refresh_screen()

    def action_refresh(self) -> None:
        """Refresh dashboard data."""
        self.refresh_screen()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
            refresh_vehicle_context_select(self)
            self.refresh_screen()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Refresh when the vehicle context changes."""
        if handle_vehicle_context_changed(self, event):
            self.refresh_screen()

    def refresh_screen(self) -> None:
        """Refresh dashboard widgets."""
        app = cast(OdometerTUI, self.app)
        data = app.get_dashboard_data()
        self.query_one("#database-path", Static).update(
            f"Database: {data.database_path}\nContext: {data.vehicle_context_label}"
        )
        self._update_metric("#vehicles", "Vehicles", str(data.vehicle_count))
        self._update_metric(
            "#total-spend", "Total spend", format_money(data.summary.total_spend_pence)
        )
        self._update_metric(
            "#fuel-spend", "Fuel spend", format_money(data.summary.fuel_spend_pence)
        )
        self._update_metric(
            "#avg-cost-mile",
            "Avg cost/mi",
            format_pence_per_mile(data.average_running_cost_per_mile_pence),
        )
        self._update_metric("#latest-mpg", "Latest MPG", format_mpg(data.latest_mpg))
        self._update_metric("#expenses", "Expenses", str(data.summary.expense_count))
        self._update_metric("#fuel-logs", "Fuel logs", str(data.summary.fuel_log_count))
        self._update_metric(
            "#monthly-avg",
            "Monthly avg",
            format_money(data.summary.average_monthly_spend_pence),
        )
        self.query_one("#monthly-spend", SimpleBarChart).update_rows(data.monthly_spend)
        self.query_one("#monthly-mileage", SimpleBarChart).update_rows(data.monthly_mileage)

    def _update_metric(self, selector: str, label: str, value: str) -> None:
        """Update one metric card using a widget selector."""
        self.query_one(selector, MetricCard).update(f"[b]{label}[/b]\n{value}")
