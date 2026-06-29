"""Shared vehicle context controls for scoped TUI screens."""

from typing import cast

from textual.screen import Screen
from textual.widgets import Select

from odometer.tui.app import VEHICLE_CONTEXT_ALL, VEHICLE_CONTEXT_ALL_LABEL, OdometerTUI

VEHICLE_CONTEXT_SELECT_ID = "vehicle-context"


def vehicle_context_select() -> Select[str]:
    """Return the shared selector used by screens that can be scoped."""
    return Select[str](
        [(VEHICLE_CONTEXT_ALL_LABEL, VEHICLE_CONTEXT_ALL)],
        prompt="Vehicle context",
        allow_blank=False,
        value=VEHICLE_CONTEXT_ALL,
        id=VEHICLE_CONTEXT_SELECT_ID,
        compact=True,
    )


def refresh_vehicle_context_select(screen: Screen[None]) -> None:
    """Refresh selector options from the current database state.

    If the selected vehicle was deleted, the context is reset to all vehicles.
    """
    app = cast(OdometerTUI, screen.app)
    options = app.get_vehicle_context_options()
    values = {value for _label, value in options}
    if app.vehicle_context_value not in values:
        app.set_vehicle_context(VEHICLE_CONTEXT_ALL)

    select = screen.query_one(f"#{VEHICLE_CONTEXT_SELECT_ID}", Select)
    select.display = app.should_show_vehicle_context_select()
    select.set_options(options)
    select.value = app.vehicle_context_value


def handle_vehicle_context_changed(screen: Screen[None], event: Select.Changed) -> bool:
    """Apply a context selector change and report whether it was handled."""
    if event.select.id != VEHICLE_CONTEXT_SELECT_ID or event.value == Select.BLANK:
        return False

    app = cast(OdometerTUI, screen.app)
    app.set_vehicle_context(str(event.value))
    return True
