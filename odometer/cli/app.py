"""Typer application."""

import typer

from odometer.cli import config_commands, expense_commands, fuel_commands, vehicle_commands
from odometer.cli.helpers import console
from odometer.cli.summary_commands import calc_app, summary_app
from odometer.db.bootstrap import initialise_database

app = typer.Typer(
    name="odometer",
    help="Track the true cost of vehicle ownership.",
    no_args_is_help=True,
)


@app.command("init")
def init_database() -> None:
    """Create or initialise the SQLite database."""
    path = initialise_database()
    console.print(f"Database initialised: [bold]{path}[/bold]")


@app.command("tui")
def run_tui() -> None:
    """Start the Textual interface."""
    initialise_database()
    from odometer.tui.app import OdometerTUI

    OdometerTUI().run()


app.add_typer(config_commands.app, name="config")
app.add_typer(vehicle_commands.app, name="vehicle")
app.add_typer(expense_commands.app, name="expense")
app.add_typer(fuel_commands.app, name="fuel")
app.add_typer(summary_app, name="summary")
app.add_typer(calc_app, name="calc")
