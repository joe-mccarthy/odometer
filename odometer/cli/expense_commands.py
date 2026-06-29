"""Expense CLI commands."""

from typing import Annotated

import typer
from rich.table import Table

from odometer.cli.helpers import cli_session, console, handle_expected_error
from odometer.services.exceptions import OdometerError
from odometer.services.expense_service import ExpenseService
from odometer.services.vehicle_service import VehicleService
from odometer.utils.dates import parse_date, parse_optional_date
from odometer.utils.formatting import format_optional_int
from odometer.utils.money import MoneyParseError, format_money, parse_money_to_pence

app = typer.Typer(help="Manage expenses.")


@app.command("add")
def add_expense(
    vehicle: Annotated[str, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")],
    category: Annotated[str, typer.Option("--category", "-c", help="Expense category.")],
    amount: Annotated[str, typer.Option("--amount", "-a", help="Amount in pounds.")],
    date_value: Annotated[
        str | None, typer.Option("--date", help="Expense date yyyy-mm-dd.")
    ] = None,
    mileage: Annotated[int | None, typer.Option("--mileage", help="Odometer mileage.")] = None,
    description: Annotated[
        str | None, typer.Option("--description", help="Short description.")
    ] = None,
    vendor: Annotated[str | None, typer.Option("--vendor", help="Vendor or payee.")] = None,
    notes: Annotated[str | None, typer.Option("--notes", help="Notes.")] = None,
) -> None:
    """Add an expense."""
    try:
        with cli_session() as session:
            expense = ExpenseService(session).add_expense(
                vehicle_identifier=vehicle,
                category=category,
                amount_pence=parse_money_to_pence(amount),
                date_=parse_date(date_value),
                odometer_miles=mileage,
                description=description,
                vendor=vendor,
                notes=notes,
            )
    except (OdometerError, MoneyParseError, ValueError) as exc:
        handle_expected_error(exc)

    console.print(
        f"Added {expense.category.value.lower()} expense for {format_money(expense.amount_pence)}."
    )


@app.command("list")
def list_expenses(
    vehicle: Annotated[
        str | None, typer.Option("--vehicle", "-v", help="Vehicle registration or id.")
    ] = None,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Expense category.")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date yyyy-mm-dd.")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date yyyy-mm-dd.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum rows.")] = 50,
) -> None:
    """List expenses."""
    try:
        with cli_session() as session:
            service = ExpenseService(session)
            expenses = service.list_expenses(
                vehicle_identifier=vehicle,
                category=category,
                date_from=parse_optional_date(date_from),
                date_to=parse_optional_date(date_to),
                limit=limit,
            )
            vehicle_service = VehicleService(session)
            registrations = {
                expense.vehicle_id: vehicle_service.get_vehicle(expense.vehicle_id).registration
                for expense in expenses
            }
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)

    if not expenses:
        console.print("No expenses found.")
        return

    table = Table(title="Expenses")
    table.add_column("ID")
    table.add_column("Date")
    table.add_column("Vehicle")
    table.add_column("Category")
    table.add_column("Amount", justify="right")
    table.add_column("Mileage", justify="right")
    table.add_column("Description")
    table.add_column("Vendor")

    for expense in expenses:
        table.add_row(
            expense.id,
            expense.date.isoformat(),
            registrations[expense.vehicle_id],
            expense.category.value,
            format_money(expense.amount_pence),
            format_optional_int(expense.odometer_miles),
            expense.description or "-",
            expense.vendor or "-",
        )
    console.print(table)


@app.command("delete")
def delete_expense(
    expense_id: Annotated[str, typer.Argument(help="Expense id.")],
) -> None:
    """Delete an expense."""
    if not typer.confirm(f"Delete expense {expense_id}?"):
        console.print("Delete cancelled.")
        return

    try:
        with cli_session() as session:
            ExpenseService(session).delete_expense(expense_id)
    except OdometerError as exc:
        handle_expected_error(exc)

    console.print(f"Deleted expense {expense_id}.")
