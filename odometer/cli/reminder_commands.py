"""Local reminder commands using shared service rules."""

from typing import Annotated

import typer

from odometer.cli.helpers import cli_session, console, handle_expected_error
from odometer.services.exceptions import OdometerError
from odometer.services.reminder_service import ReminderService
from odometer.utils.dates import parse_optional_date

app = typer.Typer(
    help=(
        "Local reminders. Due: either threshold reached. "
        "Upcoming: 30 days or 1,000 miles inclusive. "
        "Readings older than 90 days are stale."
    )
)


@app.command("add")
def add(
    vehicle: Annotated[str, typer.Option()],
    title: Annotated[str, typer.Option()],
    category: Annotated[str, typer.Option()],
    due_date: Annotated[str | None, typer.Option()] = None,
    due_mileage: Annotated[int | None, typer.Option()] = None,
) -> None:
    """Create a vehicle reminder with at least one threshold."""
    try:
        with cli_session() as session:
            row = ReminderService(session).create(
                vehicle_identifier=vehicle,
                title=title,
                category=category,
                due_date=parse_optional_date(due_date),
                due_mileage=due_mileage,
            )
            console.print(f"Added reminder {row.id}.")
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)


@app.command("edit")
def edit(
    reminder_id: str,
    title: Annotated[str, typer.Option()],
    category: Annotated[str, typer.Option()],
    due_date: Annotated[str | None, typer.Option()] = None,
    due_mileage: Annotated[int | None, typer.Option()] = None,
) -> None:
    """Replace title/category/thresholds, preserving ID and vehicle. Omitted thresholds clear."""
    try:
        with cli_session() as session:
            ReminderService(session).update(
                reminder_id=reminder_id,
                title=title,
                category=category,
                due_date=parse_optional_date(due_date),
                due_mileage=due_mileage,
            )
            console.print("Reminder updated.")
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)


@app.command("list")
def list_reminders(
    vehicle: Annotated[str | None, typer.Option()] = None,
    include_inactive: Annotated[bool, typer.Option()] = False,
    upcoming: Annotated[
        bool, typer.Option(help="Only due/upcoming/unknown active occurrences.")
    ] = False,
) -> None:
    """List active-vehicle reminders and completed history, with reading provenance."""
    try:
        with cli_session() as session:
            rows = ReminderService(session).list(
                vehicle_identifier=vehicle, include_inactive=include_inactive
            )
            for item in rows:
                if upcoming and item["status"] not in {"due", "upcoming", "unknown"}:
                    continue
                r, reading = item["reminder"], item["reading"]
                console.print(
                    f"{r.id} | {item['registration']} ({item['vehicle_status']}) | "
                    f"{r.title} | {r.category} | {item['status']} | "
                    f"date {r.due_date or '—'} | "
                    f"miles {r.due_mileage if r.due_mileage is not None else '—'}",
                    markup=False,
                )
                console.print(
                    f"Latest recorded mileage: {reading['miles']} miles; "
                    f"date {reading['date'] or 'unknown'}; source {reading['source']}. "
                    f"{reading['message']}",
                    markup=False,
                )
            if not rows:
                console.print("No reminders yet.")
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)


@app.command("complete")
def complete(
    reminder_id: str,
    next_due_date: Annotated[str | None, typer.Option()] = None,
    next_due_mileage: Annotated[int | None, typer.Option()] = None,
) -> None:
    """Retain completion history; optional next thresholds create a linked occurrence atomically."""
    try:
        with cli_session() as session:
            result = ReminderService(session).complete(
                reminder_id=reminder_id,
                next_due_date=parse_optional_date(next_due_date),
                next_due_mileage=next_due_mileage,
            )
            console.print("Reminder completed.")
            if result["next"] is not None:
                console.print(f"Next reminder: {result['next'].id}")
    except (OdometerError, ValueError) as exc:
        handle_expected_error(exc)


@app.command("delete")
def delete_reminder(reminder_id: str) -> None:
    """Delete an occurrence after confirmation."""
    if not typer.confirm(f"Delete reminder {reminder_id}?"):
        console.print("Delete cancelled.")
        return
    try:
        with cli_session() as session:
            ReminderService(session).delete(reminder_id)
            console.print("Reminder deleted.")
    except OdometerError as exc:
        handle_expected_error(exc)
