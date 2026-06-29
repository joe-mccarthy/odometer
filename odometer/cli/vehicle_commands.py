"""Vehicle CLI commands."""

from typing import Annotated

import typer
from rich.table import Table

from odometer.cli.helpers import (
    cli_session,
    console,
    format_pence_per_mile,
    handle_expected_error,
    parse_money_option,
)
from odometer.services.calculation_service import CalculationService
from odometer.services.exceptions import OdometerError
from odometer.services.vehicle_service import VehicleService
from odometer.utils.dates import parse_optional_date
from odometer.utils.formatting import format_date, format_optional_float
from odometer.utils.money import MoneyParseError, format_money

app = typer.Typer(help="Manage vehicles.")


@app.command("add")
def add_vehicle(
    registration: Annotated[
        str, typer.Option("--registration", "-r", help="Vehicle registration.")
    ],
    initial_mileage: Annotated[int, typer.Option("--initial-mileage", help="Initial mileage.")],
    fuel_tank_litres: Annotated[
        float | None,
        typer.Option("--fuel-tank-litres", help="Fuel tank capacity in litres."),
    ] = None,
    make: Annotated[str | None, typer.Option("--make", help="Vehicle make.")] = None,
    vehicle_model: Annotated[str | None, typer.Option("--model", help="Vehicle model.")] = None,
    nickname: Annotated[str | None, typer.Option("--nickname", help="Vehicle nickname.")] = None,
    year: Annotated[int | None, typer.Option("--year", help="Vehicle year.")] = None,
    purchase_date: Annotated[
        str | None, typer.Option("--purchase-date", help="Purchase date yyyy-mm-dd.")
    ] = None,
    purchase_price: Annotated[
        str | None, typer.Option("--purchase-price", help="Purchase price in pounds.")
    ] = None,
) -> None:
    """Add a vehicle."""
    try:
        with cli_session() as session:
            vehicle = VehicleService(session).create_vehicle(
                registration=registration,
                make=make,
                model=vehicle_model,
                nickname=nickname,
                year=year,
                initial_mileage=initial_mileage,
                fuel_tank_litres=fuel_tank_litres,
                purchase_date=parse_optional_date(purchase_date),
                purchase_price_pence=parse_money_option(purchase_price),
            )
    except (OdometerError, MoneyParseError, ValueError) as exc:
        handle_expected_error(exc)

    console.print(f"Added vehicle [bold]{vehicle.registration}[/bold] ({vehicle.id})")


@app.command("list")
def list_vehicles(
    include_all: Annotated[
        bool, typer.Option("--all", help="Include sold and archived vehicles.")
    ] = False,
) -> None:
    """List vehicles."""
    with cli_session() as session:
        vehicles = VehicleService(session).list_vehicles(include_inactive=include_all)
        calculations = CalculationService(session)
        metrics_by_id = {
            vehicle.id: calculations.vehicle_cost_metrics(vehicle.id)[0] for vehicle in vehicles
        }

    if not vehicles:
        console.print("No vehicles found.")
        return

    table = Table(title="Vehicles")
    table.add_column("Registration")
    table.add_column("Nickname")
    table.add_column("Make/model")
    table.add_column("Year")
    table.add_column("Status")
    table.add_column("Initial mileage", justify="right")
    table.add_column("Tank", justify="right")
    table.add_column("Latest mileage", justify="right")
    table.add_column("Total spend", justify="right")
    table.add_column("Cost/mile", justify="right")

    for vehicle in vehicles:
        metrics = metrics_by_id.get(vehicle.id)
        make_model = " ".join(part for part in [vehicle.make, vehicle.model] if part) or "-"
        table.add_row(
            vehicle.registration,
            vehicle.nickname or "-",
            make_model,
            str(vehicle.year) if vehicle.year else "-",
            vehicle.status.value,
            f"{vehicle.initial_mileage:,}",
            format_optional_float(vehicle.fuel_tank_litres, suffix=" L", precision=1),
            f"{metrics.latest_mileage:,}" if metrics else "-",
            format_money(metrics.running_cost_pence) if metrics else "-",
            format_pence_per_mile(metrics.running_cost_per_mile_pence) if metrics else "-",
        )
    console.print(table)


@app.command("show")
def show_vehicle(
    registration: Annotated[str, typer.Argument(help="Registration or vehicle id.")],
) -> None:
    """Show full vehicle details."""
    try:
        with cli_session() as session:
            vehicle = VehicleService(session).get_vehicle(registration)
            metrics = CalculationService(session).vehicle_cost_metrics(vehicle.id)[0]
    except OdometerError as exc:
        handle_expected_error(exc)

    table = Table(title=f"Vehicle {vehicle.registration}")
    table.add_column("Field")
    table.add_column("Value")
    rows = [
        ("ID", vehicle.id),
        ("Registration", vehicle.registration),
        ("Make", vehicle.make or "-"),
        ("Model", vehicle.model or "-"),
        ("Nickname", vehicle.nickname or "-"),
        ("Year", str(vehicle.year) if vehicle.year else "-"),
        ("Status", vehicle.status.value),
        ("Initial mileage", f"{vehicle.initial_mileage:,}"),
        ("Fuel tank", format_optional_float(vehicle.fuel_tank_litres, suffix=" L", precision=1)),
        ("Latest mileage", f"{metrics.latest_mileage:,}"),
        ("Purchase date", format_date(vehicle.purchase_date)),
        ("Purchase price", format_money(vehicle.purchase_price_pence)),
        ("Running cost", format_money(metrics.running_cost_pence)),
        ("Running cost per mile", format_pence_per_mile(metrics.running_cost_per_mile_pence)),
        ("Ownership cost per mile", format_pence_per_mile(metrics.ownership_cost_per_mile_pence)),
    ]
    for field, value in rows:
        table.add_row(field, value)
    console.print(table)


@app.command("set-fuel-tank")
def set_fuel_tank(
    registration: Annotated[str, typer.Argument(help="Registration or vehicle id.")],
    litres: Annotated[float, typer.Option("--litres", help="Fuel tank capacity in litres.")],
) -> None:
    """Set a vehicle fuel tank capacity."""
    try:
        with cli_session() as session:
            vehicle = VehicleService(session).set_fuel_tank_capacity(registration, litres)
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)
    console.print(f"Updated fuel tank for [bold]{vehicle.registration}[/bold] to {litres:.1f} L.")


@app.command("archive")
def archive_vehicle(
    registration: Annotated[str, typer.Argument(help="Registration or vehicle id.")],
) -> None:
    """Archive a vehicle."""
    try:
        with cli_session() as session:
            vehicle = VehicleService(session).archive_vehicle(registration)
    except OdometerError as exc:
        handle_expected_error(exc)
    console.print(f"Archived vehicle [bold]{vehicle.registration}[/bold].")


@app.command("sold")
def mark_vehicle_sold(
    registration: Annotated[str, typer.Argument(help="Registration or vehicle id.")],
) -> None:
    """Mark a vehicle as sold."""
    try:
        with cli_session() as session:
            vehicle = VehicleService(session).mark_vehicle_sold(registration)
    except OdometerError as exc:
        handle_expected_error(exc)
    console.print(f"Marked vehicle [bold]{vehicle.registration}[/bold] as sold.")


@app.command("delete")
def delete_vehicle(
    registration: Annotated[str, typer.Argument(help="Registration or vehicle id.")],
) -> None:
    """Delete a vehicle and all associated data."""
    try:
        with cli_session() as session:
            service = VehicleService(session)
            vehicle = service.get_vehicle(registration)
            if not typer.confirm(
                f"Delete vehicle {vehicle.registration} and all associated expenses and fuel logs?"
            ):
                console.print("Delete cancelled.")
                return
            result = service.delete_vehicle(vehicle.id)
    except OdometerError as exc:
        handle_expected_error(exc)

    console.print(
        f"Deleted vehicle [bold]{result.registration}[/bold], "
        f"{result.expense_count} expenses, and {result.fuel_log_count} fuel logs."
    )
