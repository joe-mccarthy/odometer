"""Vehicles screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from odometer.cli.helpers import format_pence_per_mile
from odometer.services.exceptions import OdometerError
from odometer.tui.app import OdometerTUI
from odometer.tui.screens.confirm import ConfirmDeleteModal
from odometer.tui.screens.tables import replace_table_data
from odometer.tui.screens.vehicle_detail import VehicleDetailScreen
from odometer.utils.formatting import format_optional_float
from odometer.utils.money import MoneyParseError, format_money


class VehiclesScreen(Screen[None]):
    """Vehicle overview screen."""

    BINDINGS = [
        ("a", "add_vehicle", "Add"),
        ("delete", "delete_selected", "Delete"),
        ("enter", "open_selected", "Open"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        """Initialise row id tracking for open and delete operations."""
        super().__init__()
        self.vehicle_ids: list[str] = []
        self.vehicle_registrations: list[str] = []

    def compose(self) -> ComposeResult:
        """Build the vehicle overview table screen."""
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Vehicles[/b]", classes="section")
            yield Static("", id="message")
            yield DataTable(id="vehicles-table")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the table."""
        table = self.query_one("#vehicles-table", DataTable)
        table.cursor_type = "row"
        self.refresh_table()

    def refresh_table(self) -> None:
        """Refresh vehicle rows."""
        app = cast(OdometerTUI, self.app)
        rows = app.get_vehicle_rows()
        self.vehicle_ids = []
        self.vehicle_registrations = []
        table = self.query_one("#vehicles-table", DataTable)
        columns = (
            "Registration",
            "Nickname",
            "Make/model",
            "Year",
            "Status",
            "Initial",
            "Tank",
            "Latest",
            "Spend",
            "Cost/mile",
        )
        if not rows:
            replace_table_data(table, columns, ())
            self.query_one("#message", Static).update("No vehicles found.")
            return

        self.query_one("#message", Static).update("")
        table_rows = []
        for row in rows:
            vehicle = row.metrics.vehicle
            self.vehicle_ids.append(vehicle.id)
            self.vehicle_registrations.append(vehicle.registration)
            make_model = " ".join(part for part in [vehicle.make, vehicle.model] if part) or "-"
            table_rows.append(
                (
                    vehicle.registration,
                    vehicle.nickname or "-",
                    make_model,
                    str(vehicle.year) if vehicle.year else "-",
                    vehicle.status.value,
                    f"{vehicle.initial_mileage:,}",
                    format_optional_float(vehicle.fuel_tank_litres, suffix=" L", precision=1),
                    f"{row.metrics.latest_mileage:,}",
                    format_money(row.metrics.running_cost_pence),
                    format_pence_per_mile(row.metrics.running_cost_per_mile_pence),
                )
            )
        replace_table_data(table, columns, table_rows)

    def action_refresh(self) -> None:
        """Refresh table."""
        self.refresh_table()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
            self.refresh_table()

    def action_open_selected(self) -> None:
        """Open the selected vehicle."""
        table = self.query_one("#vehicles-table", DataTable)
        if not self.vehicle_ids or table.cursor_row >= len(self.vehicle_ids):
            return
        self.app.push_screen(VehicleDetailScreen(self.vehicle_ids[table.cursor_row]))

    def action_add_vehicle(self) -> None:
        """Open add vehicle modal."""
        self.app.push_screen(AddVehicleModal(), callback=self._after_add)

    def action_delete_selected(self) -> None:
        """Confirm deletion of the selected vehicle."""
        table = self.query_one("#vehicles-table", DataTable)
        if not self.vehicle_ids or table.cursor_row >= len(self.vehicle_ids):
            return
        vehicle_id = self.vehicle_ids[table.cursor_row]
        registration = self.vehicle_registrations[table.cursor_row]
        self.app.push_screen(
            ConfirmDeleteModal(
                "Delete vehicle",
                f"Delete {registration} and all associated expenses and fuel logs?",
            ),
            callback=lambda confirmed: self._after_delete(vehicle_id, confirmed),
        )

    def _after_add(self, saved: bool | None) -> None:
        """Refresh the table after a modal saves a new vehicle."""
        if saved:
            self.refresh_table()

    def _after_delete(self, vehicle_id: str, confirmed: bool | None) -> None:
        """Delete a vehicle after confirmation and refresh table state."""
        if not confirmed:
            self.query_one("#message", Static).update("Delete cancelled.")
            return
        try:
            app = cast(OdometerTUI, self.app)
            result = app.delete_vehicle(vehicle_id)
        except OdometerError as exc:
            self.query_one("#message", Static).update(str(exc))
            return
        self.refresh_table()
        self.query_one("#message", Static).update(
            f"Deleted {result.registration}, {result.expense_count} expenses, "
            f"and {result.fuel_log_count} fuel logs."
        )


class AddVehicleModal(ModalScreen[bool]):
    """Simple add vehicle form."""

    def compose(self) -> ComposeResult:
        """Build input widgets for creating a vehicle."""
        with Container(id="content"):
            yield Static("[b]Add vehicle[/b]")
            yield Input(placeholder="Registration", id="registration")
            yield Input(placeholder="Make", id="make")
            yield Input(placeholder="Model", id="model")
            yield Input(placeholder="Nickname", id="nickname")
            yield Input(placeholder="Year", id="year")
            yield Input(placeholder="Initial mileage", id="initial_mileage")
            yield Input(placeholder="Fuel tank litres", id="fuel_tank_litres")
            yield Input(placeholder="Purchase date yyyy-mm-dd", id="purchase_date")
            yield Input(placeholder="Purchase price", id="purchase_price")
            yield Static("", id="message")
            yield Button("Save", id="save", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle form buttons."""
        if event.button.id == "cancel":
            self.dismiss(False)
            return
        try:
            app = cast(OdometerTUI, self.app)
            app.add_vehicle_from_form(
                {
                    "registration": self.query_one("#registration", Input).value,
                    "make": self.query_one("#make", Input).value,
                    "model": self.query_one("#model", Input).value,
                    "nickname": self.query_one("#nickname", Input).value,
                    "year": self.query_one("#year", Input).value,
                    "initial_mileage": self.query_one("#initial_mileage", Input).value,
                    "fuel_tank_litres": self.query_one("#fuel_tank_litres", Input).value,
                    "purchase_date": self.query_one("#purchase_date", Input).value,
                    "purchase_price": self.query_one("#purchase_price", Input).value,
                }
            )
        except (OdometerError, MoneyParseError, ValueError) as exc:
            self.query_one("#message", Static).update(str(exc))
            return
        self.dismiss(True)
