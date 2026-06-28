"""Dashboard screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from odometer.cli.helpers import format_mpg, format_pence_per_mile
from odometer.tui.app import OdometerTUI
from odometer.tui.widgets.metric_card import MetricCard
from odometer.tui.widgets.simple_bar_chart import SimpleBarChart
from odometer.utils.money import format_money


class DashboardScreen(Screen[None]):
    """Interactive dashboard."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Odometer[/b]", classes="section")
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
            yield SimpleBarChart("Monthly spend", [], id="monthly-spend")
        yield Footer()

    def on_mount(self) -> None:
        """Populate dashboard data."""
        self.refresh_screen()

    def action_refresh(self) -> None:
        """Refresh dashboard data."""
        self.refresh_screen()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
            self.refresh_screen()

    def refresh_screen(self) -> None:
        """Refresh dashboard widgets."""
        app = cast(OdometerTUI, self.app)
        data = app.get_dashboard_data()
        self.query_one("#database-path", Static).update(f"Database: {data.database_path}")
        self._update_metric("#vehicles", "Vehicles", str(data.active_vehicle_count))
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

    def _update_metric(self, selector: str, label: str, value: str) -> None:
        self.query_one(selector, MetricCard).update(f"[b]{label}[/b]\n{value}")
