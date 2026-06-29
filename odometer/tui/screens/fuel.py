"""Fuel screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from odometer.services.exceptions import OdometerError
from odometer.tui.app import OdometerTUI
from odometer.tui.screens.confirm import ConfirmDeleteModal
from odometer.tui.screens.context import (
    handle_vehicle_context_changed,
    refresh_vehicle_context_select,
    vehicle_context_select,
)
from odometer.tui.screens.tables import replace_table_data
from odometer.utils.money import MoneyParseError, format_money


class FuelScreen(Screen[None]):
    """Fuel log table screen."""

    BINDINGS = [
        ("a", "add_fuel", "Add"),
        ("delete", "delete_selected", "Delete"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        """Initialise row id tracking for delete operations."""
        super().__init__()
        self.fuel_log_ids: list[str] = []

    def compose(self) -> ComposeResult:
        """Build the fuel log table screen and vehicle context selector."""
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Fuel logs[/b]", classes="section")
            yield vehicle_context_select()
            yield Static("", id="message")
            yield DataTable(id="fuel-table")
        yield Footer()

    def on_mount(self) -> None:
        """Populate table."""
        table = self.query_one("#fuel-table", DataTable)
        table.cursor_type = "row"
        refresh_vehicle_context_select(self)
        self.refresh_table()

    def refresh_table(self) -> None:
        """Refresh fuel logs."""
        app = cast(OdometerTUI, self.app)
        rows = app.get_fuel_logs()
        self.fuel_log_ids = []
        table = self.query_one("#fuel-table", DataTable)
        if not rows:
            replace_table_data(
                table,
                ("Date", "Registration", "Mileage", "Litres", "Amount", "Fill", "Station"),
                (),
            )
            self.query_one("#message", Static).update("No fuel logs found.")
            return
        self.query_one("#message", Static).update("")
        table_rows = []
        for row in rows:
            fuel_log = row.fuel_log
            self.fuel_log_ids.append(fuel_log.id)
            table_rows.append(
                (
                    fuel_log.date.isoformat(),
                    row.registration,
                    f"{fuel_log.odometer_miles:,}",
                    f"{fuel_log.litres:.2f}",
                    format_money(fuel_log.total_cost_pence),
                    "Full" if fuel_log.is_full_tank else "Partial",
                    fuel_log.station or "-",
                )
            )
        replace_table_data(
            table,
            ("Date", "Registration", "Mileage", "Litres", "Amount", "Fill", "Station"),
            table_rows,
        )

    def action_refresh(self) -> None:
        """Refresh table."""
        self.refresh_table()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
            refresh_vehicle_context_select(self)
            self.refresh_table()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Refresh when the vehicle context changes."""
        if handle_vehicle_context_changed(self, event):
            self.refresh_table()

    def action_add_fuel(self) -> None:
        """Open add fuel modal."""
        self.app.push_screen(AddFuelModal(), callback=self._after_add)

    def action_delete_selected(self) -> None:
        """Confirm deletion of the selected fuel log."""
        table = self.query_one("#fuel-table", DataTable)
        if not self.fuel_log_ids or table.cursor_row >= len(self.fuel_log_ids):
            return
        fuel_log_id = self.fuel_log_ids[table.cursor_row]
        self.app.push_screen(
            ConfirmDeleteModal("Delete fuel log", "Delete the selected fuel log?"),
            callback=lambda confirmed: self._after_delete(fuel_log_id, confirmed),
        )

    def _after_add(self, saved: bool | None) -> None:
        """Refresh the table after a modal saves a new fuel log."""
        if saved:
            self.refresh_table()

    def _after_delete(self, fuel_log_id: str, confirmed: bool | None) -> None:
        """Delete a fuel log after confirmation and refresh table state."""
        if not confirmed:
            self.query_one("#message", Static).update("Delete cancelled.")
            return
        try:
            app = cast(OdometerTUI, self.app)
            app.delete_fuel_log(fuel_log_id)
        except OdometerError as exc:
            self.query_one("#message", Static).update(str(exc))
            return
        self.refresh_table()
        self.query_one("#message", Static).update("Fuel log deleted.")


class AddFuelModal(ModalScreen[bool]):
    """Simple add fuel form."""

    def compose(self) -> ComposeResult:
        """Build input widgets for creating a fuel log."""
        with Container(id="content"):
            yield Static("[b]Add fuel[/b]")
            yield Input(placeholder="Vehicle registration or id", id="vehicle")
            yield Input(placeholder="Litres", id="litres")
            yield Input(placeholder="Amount", id="amount")
            yield Input(placeholder="Mileage", id="mileage")
            yield Input(placeholder="Date yyyy-mm-dd", id="date")
            yield Input(placeholder="Station", id="station")
            yield Input(placeholder="Fill: full or partial", id="fill")
            yield Static("", id="message")
            yield Button("Save", id="save", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle buttons."""
        if event.button.id == "cancel":
            self.dismiss(False)
            return
        try:
            app = cast(OdometerTUI, self.app)
            app.add_fuel_from_form(
                {
                    "vehicle": self.query_one("#vehicle", Input).value,
                    "litres": self.query_one("#litres", Input).value,
                    "amount": self.query_one("#amount", Input).value,
                    "mileage": self.query_one("#mileage", Input).value,
                    "date": self.query_one("#date", Input).value,
                    "station": self.query_one("#station", Input).value,
                    "fill": self.query_one("#fill", Input).value,
                }
            )
        except (OdometerError, MoneyParseError, ValueError) as exc:
            self.query_one("#message", Static).update(str(exc))
            return
        self.dismiss(True)
