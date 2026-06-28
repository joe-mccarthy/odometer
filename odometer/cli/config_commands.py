"""Configuration commands."""

import typer
from rich.table import Table

from odometer.cli.helpers import console
from odometer.db.session import DB_PATH_ENV, get_app_data_dir, get_database_path

app = typer.Typer(help="Show Odometer configuration.")


@app.command("show")
def show_config() -> None:
    """Show current configuration."""
    table = Table(title="Odometer configuration")
    table.add_column("Setting")
    table.add_column("Value")
    table.add_row("Database path", str(get_database_path()))
    table.add_row("App data directory", str(get_app_data_dir()))
    table.add_row("Database override", DB_PATH_ENV)
    console.print(table)
