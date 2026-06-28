"""Summaries screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from odometer.cli.helpers import format_pence_per_mile
from odometer.tui.app import OdometerTUI, SummariesData
from odometer.tui.widgets.simple_bar_chart import SimpleBarChart
from odometer.utils.formatting import format_optional_int
from odometer.utils.money import format_money


class SummariesScreen(Screen[None]):
    """Cost summaries screen."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Summaries[/b]", classes="section")
            yield Static("[b]Category breakdown[/b]", classes="section")
            yield DataTable(id="categories-table")
            yield SimpleBarChart("Monthly spend", [], id="monthly-chart")
            yield Static("[b]Monthly[/b]", classes="section")
            yield DataTable(id="monthly-table")
            yield Static("[b]Annual[/b]", classes="section")
            yield DataTable(id="annual-table")
        yield Footer()

    def on_mount(self) -> None:
        """Populate summaries."""
        self.refresh_screen()

    def action_refresh(self) -> None:
        """Refresh summaries."""
        self.refresh_screen()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
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
        self.query_one("#monthly-chart", SimpleBarChart).update_rows(chart_rows)

    def _refresh_categories(self, data: SummariesData) -> None:
        summaries = data
        table = self.query_one("#categories-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Category", "Amount", "Share", "Count")
        for row in summaries.categories:
            table.add_row(
                row.category.value,
                format_money(row.amount_pence),
                f"{row.percentage:.1f}%",
                str(row.count),
            )

    def _refresh_monthly(self, data: SummariesData) -> None:
        summaries = data
        table = self.query_one("#monthly-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Period", "Total", "Fuel", "Expenses", "Miles", "Cost/mile")
        for row in summaries.monthly:
            table.add_row(
                row.period,
                format_money(row.total_spend_pence),
                format_money(row.fuel_spend_pence),
                format_money(row.expense_spend_pence),
                format_optional_int(row.miles_driven),
                format_pence_per_mile(row.cost_per_mile_pence),
            )

    def _refresh_annual(self, data: SummariesData) -> None:
        summaries = data
        table = self.query_one("#annual-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Period", "Total", "Fuel", "Expenses", "Miles", "Cost/mile")
        for row in summaries.annual:
            table.add_row(
                row.period,
                format_money(row.total_spend_pence),
                format_money(row.fuel_spend_pence),
                format_money(row.expense_spend_pence),
                format_optional_int(row.miles_driven),
                format_pence_per_mile(row.cost_per_mile_pence),
            )
