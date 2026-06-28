"""CLI helper functions."""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import ROUND_HALF_UP, Decimal
from typing import NoReturn

import typer
from rich.console import Console
from sqlmodel import Session

from odometer.db.bootstrap import initialise_database
from odometer.db.session import get_session
from odometer.services.exceptions import OdometerError
from odometer.utils.money import MoneyParseError, parse_money_to_pence

console = Console()


@contextmanager
def cli_session() -> Iterator[Session]:
    """Initialise the database and yield a session."""
    initialise_database()
    with get_session() as session:
        yield session


def abort(message: str) -> NoReturn:
    """Print a clean CLI error and exit."""
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code=1)


def handle_expected_error(exc: OdometerError | MoneyParseError | ValueError) -> NoReturn:
    """Handle expected validation errors."""
    abort(str(exc))


def parse_money_option(value: str | None) -> int | None:
    """Parse an optional money option."""
    if value is None:
        return None
    return parse_money_to_pence(value)


def format_pence_per_mile(value: float | None) -> str:
    """Format pence per mile as GBP per mile."""
    if value is None:
        return "-"
    pounds = (Decimal(str(value)) / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"£{pounds}/mile"


def format_mpg(value: float | None) -> str:
    """Format UK MPG."""
    return "-" if value is None else f"{value:.1f} mpg"
