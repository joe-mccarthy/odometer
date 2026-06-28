"""Fuel CLI commands."""

from typing import Annotated

import typer
from rich.table import Table

from odometer.cli.helpers import cli_session, console, handle_expected_error
from odometer.services.exceptions import OdometerError
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService
from odometer.utils.dates import parse_date, parse_optional_date
from odometer.utils.money import MoneyParseError, format_money, parse_money_to_pence

app = typer.Typer(help="Manage fuel logs.")


@app.command("add")
def add_fuel(
    vehicle: Annotated[str, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")],
    litres: Annotated[float, typer.Option("--litres", help="Fuel quantity in litres.")],
    amount: Annotated[str, typer.Option("--amount", help="Total amount in pounds.")],
    mileage: Annotated[int, typer.Option("--mileage", help="Odometer mileage.")],
    fuel_tank_litres: Annotated[
        float | None,
        typer.Option(
            "--fuel-tank-litres",
            help="Vehicle fuel tank capacity in litres if not already set.",
        ),
    ] = None,
    date_value: Annotated[str | None, typer.Option("--date", help="Fuel date yyyy-mm-dd.")] = None,
    station: Annotated[str | None, typer.Option("--station", help="Fuel station.")] = None,
    full: Annotated[bool, typer.Option("--full/--partial", help="Full or partial fill.")] = True,
    notes: Annotated[str | None, typer.Option("--notes", help="Notes.")] = None,
) -> None:
    """Add a fuel log."""
    try:
        with cli_session() as session:
            fuel_log = FuelService(session).add_fuel_log(
                vehicle_identifier=vehicle,
                litres=litres,
                total_cost_pence=parse_money_to_pence(amount),
                odometer_miles=mileage,
                date_=parse_date(date_value),
                station=station,
                is_full_tank=full,
                notes=notes,
                fuel_tank_litres=fuel_tank_litres,
            )
    except (OdometerError, MoneyParseError, ValueError) as exc:
        handle_expected_error(exc)

    console.print(f"Added fuel log for {format_money(fuel_log.total_cost_pence)}.")


@app.command("list")
def list_fuel(
    vehicle: Annotated[
        str | None, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date yyyy-mm-dd.")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date yyyy-mm-dd.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum rows.")] = 50,
) -> None:
    """List fuel logs."""
    try:
        with cli_session() as session:
            service = FuelService(session)
            fuel_logs = service.list_fuel_logs(
                vehicle_identifier=vehicle,
                date_from=parse_optional_date(date_from),
                date_to=parse_optional_date(date_to),
                limit=limit,
            )
            vehicle_service = VehicleService(session)
            registrations = {
                fuel_log.vehicle_id: vehicle_service.get_vehicle(fuel_log.vehicle_id).registration
                for fuel_log in fuel_logs
            }
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)

    if not fuel_logs:
        console.print("No fuel logs found.")
        return

    table = Table(title="Fuel logs")
    table.add_column("Date")
    table.add_column("Vehicle")
    table.add_column("Mileage", justify="right")
    table.add_column("Litres", justify="right")
    table.add_column("Amount", justify="right")
    table.add_column("Pence/litre", justify="right")
    table.add_column("Fill")
    table.add_column("Station")

    for fuel_log in fuel_logs:
        table.add_row(
            fuel_log.date.isoformat(),
            registrations[fuel_log.vehicle_id],
            f"{fuel_log.odometer_miles:,}",
            f"{fuel_log.litres:.2f}",
            format_money(fuel_log.total_cost_pence),
            f"{fuel_log.price_per_litre_pence:.1f}" if fuel_log.price_per_litre_pence else "-",
            "Full" if fuel_log.is_full_tank else "Partial",
            fuel_log.station or "-",
        )
    console.print(table)
