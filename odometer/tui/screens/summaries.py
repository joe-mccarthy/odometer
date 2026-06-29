"""Summaries screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Select, Static

from odometer.cli.helpers import format_pence_per_mile
from odometer.tui.app import OdometerTUI, SummariesData
from odometer.tui.screens.context import (
    handle_vehicle_context_changed,
    refresh_vehicle_context_select,
    vehicle_context_select,
)
from odometer.tui.screens.tables import replace_table_data
from odometer.tui.widgets.simple_bar_chart import SimpleBarChart
from odometer.utils.formatting import format_miles, format_optional_int
from odometer.utils.money import format_money


class SummariesScreen(Screen[None]):
    """Cost summaries screen."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Build summary tables and monthly spend/mileage charts."""
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Summaries[/b]", classes="section")
            yield vehicle_context_select()
            yield Static("[b]Category breakdown[/b]", classes="section")
            yield DataTable(id="categories-table")
            with Container(classes="charts"):
                yield SimpleBarChart("Monthly spend", [], id="monthly-chart")
                yield SimpleBarChart(
                    "Monthly mileage",
                    [],
                    value_formatter=format_miles,
                    id="monthly-mileage-chart",
                )
            yield Static("[b]Monthly[/b]", classes="section")
            yield DataTable(id="monthly-table")
            yield Static("[b]Annual[/b]", classes="section")
            yield DataTable(id="annual-table")
        yield Footer()

    def on_mount(self) -> None:
        """Populate summaries."""
        refresh_vehicle_context_select(self)
        self.refresh_screen()

    def action_refresh(self) -> None:
        """Refresh summaries."""
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
        """Refresh all summary widgets."""
        app = cast(OdometerTUI, self.app)
        data = app.get_summaries_data()
        self._refresh_categories(data)
        self._refresh_monthly(data)
        self._refresh_annual(data)
        chart_rows = [
            (row.period[5:], row.total_spend_pence)
            for row in data.monthly
            if row.total_spend_pence > 0
        ]
        mileage_chart_rows = [
            (row.period[5:], row.miles_driven)
            for row in data.monthly
            if row.miles_driven is not None and row.miles_driven > 0
        ]
        self.query_one("#monthly-chart", SimpleBarChart).update_rows(chart_rows)
        self.query_one("#monthly-mileage-chart", SimpleBarChart).update_rows(mileage_chart_rows)

    def _refresh_categories(self, data: SummariesData) -> None:
        """Rebuild the category breakdown table."""
        summaries = data
        table = self.query_one("#categories-table", DataTable)
        table_rows = [
            (
                summaries.vehicle_label,
                row.category.value,
                format_money(row.amount_pence),
                f"{row.percentage:.1f}%",
                str(row.count),
            )
            for row in summaries.categories
        ]
        replace_table_data(
            table,
            ("Registration", "Category", "Amount", "Share", "Count"),
            table_rows,
        )

    def _refresh_monthly(self, data: SummariesData) -> None:
        """Rebuild the monthly summary table."""
        summaries = data
        table = self.query_one("#monthly-table", DataTable)
        table_rows = [
            (
                summaries.vehicle_label,
                row.period,
                format_money(row.total_spend_pence),
                format_money(row.fuel_spend_pence),
                format_money(row.expense_spend_pence),
                format_optional_int(row.miles_driven),
                format_pence_per_mile(row.cost_per_mile_pence),
            )
            for row in summaries.monthly
        ]
        replace_table_data(
            table,
            ("Registration", "Period", "Total", "Fuel", "Expenses", "Miles", "Cost/mile"),
            table_rows,
        )

    def _refresh_annual(self, data: SummariesData) -> None:
        """Rebuild the annual summary table."""
        summaries = data
        table = self.query_one("#annual-table", DataTable)
        table_rows = [
            (
                summaries.vehicle_label,
                row.period,
                format_money(row.total_spend_pence),
                format_money(row.fuel_spend_pence),
                format_money(row.expense_spend_pence),
                format_optional_int(row.miles_driven),
                format_pence_per_mile(row.cost_per_mile_pence),
            )
            for row in summaries.annual
        ]
        replace_table_data(
            table,
            ("Registration", "Period", "Total", "Fuel", "Expenses", "Miles", "Cost/mile"),
            table_rows,
        )
