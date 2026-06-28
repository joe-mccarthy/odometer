"""Fuel screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from odometer.services.exceptions import OdometerError
from odometer.tui.app import OdometerTUI
from odometer.utils.money import MoneyParseError, format_money


class FuelScreen(Screen[None]):
    """Fuel log table screen."""

    BINDINGS = [
        ("a", "add_fuel", "Add"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Fuel logs[/b]", classes="section")
            yield Static("", id="message")
            yield DataTable(id="fuel-table")
        yield Footer()

    def on_mount(self) -> None:
        """Populate table."""
        self.refresh_table()

    def refresh_table(self) -> None:
        """Refresh fuel logs."""
        app = cast(OdometerTUI, self.app)
        rows = app.get_fuel_logs()
        table = self.query_one("#fuel-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Vehicle", "Mileage", "Litres", "Amount", "Fill", "Station")
        if not rows:
            self.query_one("#message", Static).update("No fuel logs found.")
            return
        self.query_one("#message", Static).update("")
        for row in rows:
            fuel_log = row.fuel_log
            table.add_row(
                fuel_log.date.isoformat(),
                row.registration,
                f"{fuel_log.odometer_miles:,}",
                f"{fuel_log.litres:.2f}",
                format_money(fuel_log.total_cost_pence),
                "Full" if fuel_log.is_full_tank else "Partial",
                fuel_log.station or "-",
            )

    def action_refresh(self) -> None:
        """Refresh table."""
        self.refresh_table()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
            self.refresh_table()

    def action_add_fuel(self) -> None:
        """Open add fuel modal."""
        self.app.push_screen(AddFuelModal(), callback=self._after_add)

    def _after_add(self, saved: bool | None) -> None:
        if saved:
            self.refresh_table()


class AddFuelModal(ModalScreen[bool]):
    """Simple add fuel form."""

    def compose(self) -> ComposeResult:
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
