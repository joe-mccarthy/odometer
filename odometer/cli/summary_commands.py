"""Summary and calculation CLI commands."""

from typing import Annotated

import typer
from rich.table import Table

from odometer.cli.helpers import (
    cli_session,
    console,
    format_mpg,
    format_pence_per_mile,
    handle_expected_error,
)
from odometer.services.calculation_service import CalculationService, PeriodSummary
from odometer.services.exceptions import CalculationUnavailableError, OdometerError
from odometer.services.summary_service import OverallSummary, SummaryService
from odometer.utils.dates import parse_optional_date
from odometer.utils.formatting import format_optional_int
from odometer.utils.money import format_money

summary_app = typer.Typer(help="Show cost summaries.")
calc_app = typer.Typer(help="Run calculations.")


@summary_app.callback(invoke_without_command=True)
def summary(
    ctx: typer.Context,
    vehicle: Annotated[
        str | None, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date yyyy-mm-dd.")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date yyyy-mm-dd.")] = None,
) -> None:
    """Show an overall cost summary."""
    if ctx.invoked_subcommand is not None:
        return

    try:
        with cli_session() as session:
            result = SummaryService(session).overall_summary(
                vehicle_identifier=vehicle,
                date_from=parse_optional_date(date_from),
                date_to=parse_optional_date(date_to),
            )
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)

    _print_overall_summary(result)


@summary_app.command("monthly")
def monthly_summary(
    vehicle: Annotated[
        str | None, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")
    ] = None,
    year: Annotated[int | None, typer.Option("--year", help="Year to show.")] = None,
) -> None:
    """Show monthly spend."""
    try:
        with cli_session() as session:
            rows = SummaryService(session).monthly_summary(vehicle_identifier=vehicle, year=year)
    except OdometerError as exc:
        handle_expected_error(exc)
    _print_period_table("Monthly spend", rows)


@summary_app.command("annual")
def annual_summary(
    vehicle: Annotated[
        str | None, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")
    ] = None,
) -> None:
    """Show annual spend."""
    try:
        with cli_session() as session:
            rows = SummaryService(session).annual_summary(vehicle_identifier=vehicle)
    except OdometerError as exc:
        handle_expected_error(exc)
    _print_period_table("Annual spend", rows)


@summary_app.command("categories")
def category_summary(
    vehicle: Annotated[
        str | None, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date yyyy-mm-dd.")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date yyyy-mm-dd.")] = None,
) -> None:
    """Show category breakdown."""
    try:
        with cli_session() as session:
            rows = SummaryService(session).category_breakdown(
                vehicle_identifier=vehicle,
                date_from=parse_optional_date(date_from),
                date_to=parse_optional_date(date_to),
            )
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)

    if not rows:
        console.print("No spend found.")
        return

    table = Table(title="Category breakdown")
    table.add_column("Category")
    table.add_column("Amount", justify="right")
    table.add_column("Share", justify="right")
    table.add_column("Count", justify="right")
    for row in rows:
        table.add_row(
            row.category.value,
            format_money(row.amount_pence),
            f"{row.percentage:.1f}%",
            str(row.count),
        )
    console.print(table)


@calc_app.command("mpg")
def mpg(
    vehicle: Annotated[str, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")],
) -> None:
    """Show UK MPG fuel economy."""
    try:
        with cli_session() as session:
            stats = CalculationService(session).mpg_stats(vehicle)
    except CalculationUnavailableError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        return
    except OdometerError as exc:
        handle_expected_error(exc)

    table = Table(title="UK MPG")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Latest", format_mpg(stats.latest_mpg))
    table.add_row("Average", format_mpg(stats.average_mpg))
    table.add_row("Best", format_mpg(stats.best_mpg))
    table.add_row("Worst", format_mpg(stats.worst_mpg))
    table.add_row("Closed full-to-full segments", str(stats.segment_count))
    console.print(table)


@calc_app.command("cost-per-mile")
def cost_per_mile(
    vehicle: Annotated[
        str | None, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")
    ] = None,
) -> None:
    """Show running and ownership cost per mile."""
    try:
        with cli_session() as session:
            metrics = CalculationService(session).vehicle_cost_metrics(vehicle)
    except OdometerError as exc:
        handle_expected_error(exc)

    if not metrics:
        console.print("No vehicles found.")
        return

    table = Table(title="Cost per mile")
    table.add_column("Vehicle")
    table.add_column("Miles driven", justify="right")
    table.add_column("Running cost/mile", justify="right")
    table.add_column("Ownership cost/mile", justify="right")
    for row in metrics:
        table.add_row(
            row.vehicle.registration,
            f"{row.miles_driven:,}",
            format_pence_per_mile(row.running_cost_per_mile_pence),
            format_pence_per_mile(row.ownership_cost_per_mile_pence),
        )
    console.print(table)


def _print_overall_summary(result: OverallSummary) -> None:
    """Render the aggregate summary as a Rich table for the CLI."""
    table = Table(title="Cost summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Total spend", format_money(result.total_spend_pence))
    table.add_row("Fuel spend", format_money(result.fuel_spend_pence))
    table.add_row("Non-fuel spend", format_money(result.non_fuel_spend_pence))
    table.add_row("Expenses", str(result.expense_count))
    table.add_row("Fuel logs", str(result.fuel_log_count))
    table.add_row("Miles driven", format_optional_int(result.miles_driven))
    table.add_row(
        "Running cost per mile",
        format_pence_per_mile(result.running_cost_per_mile_pence),
    )
    table.add_row(
        "Ownership cost per mile", format_pence_per_mile(result.ownership_cost_per_mile_pence)
    )
    table.add_row("Average monthly spend", format_money(result.average_monthly_spend_pence))
    console.print(table)


def _print_period_table(title: str, rows: list[PeriodSummary]) -> None:
    """Render monthly or annual period summaries as a Rich table."""
    table = Table(title=title)
    table.add_column("Period")
    table.add_column("Total", justify="right")
    table.add_column("Fuel", justify="right")
    table.add_column("Expenses", justify="right")
    table.add_column("Miles", justify="right")
    table.add_column("Cost/mile", justify="right")
    for row in rows:
        table.add_row(
            row.period,
            format_money(row.total_spend_pence),
            format_money(row.fuel_spend_pence),
            format_money(row.expense_spend_pence),
            format_optional_int(row.miles_driven),
            format_pence_per_mile(row.cost_per_mile_pence),
        )
    console.print(table)
