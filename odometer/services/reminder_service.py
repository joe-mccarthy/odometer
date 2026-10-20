"""Shared reminder rules for CLI and HTTP; no notifications or recurrence scheduler."""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, col, select

from odometer.models import Expense, ExpenseCategory, FuelLog, Reminder, Vehicle, VehicleStatus
from odometer.services.exceptions import ReminderNotFoundError
from odometer.services.vehicle_service import VehicleService


class ReminderService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def validate(
        title: str, category: str, due_date: date | None, due_mileage: int | None
    ) -> ExpenseCategory:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Title must not be blank.")
        if due_date is not None and (type(due_date) is not date):
            raise ValueError("Use a calendar due date.")
        if due_mileage is not None and (
            type(due_mileage) is not int or not 0 <= due_mileage <= 9007199254740991
        ):
            raise ValueError("Due mileage must be a nonnegative safe whole number.")
        if due_date is None and due_mileage is None:
            raise ValueError("Supply at least one due date or due mileage.")
        return ExpenseCategory.from_input(category)

    def get(self, reminder_id: str) -> Reminder:
        row = self.session.get(Reminder, reminder_id)
        if row is None:
            raise ReminderNotFoundError("Reminder not found.")
        return row

    def create(
        self,
        *,
        vehicle_identifier: str,
        title: str,
        category: str,
        due_date: date | None = None,
        due_mileage: int | None = None,
    ) -> Reminder:
        parsed = self.validate(title, category, due_date, due_mileage)
        vehicle = VehicleService(self.session).get_vehicle(vehicle_identifier)
        row = Reminder(
            vehicle_id=vehicle.id,
            title=title.strip(),
            category=parsed,
            due_date=due_date,
            due_mileage=due_mileage,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def update(
        self,
        *,
        reminder_id: str,
        title: str,
        category: str,
        due_date: date | None = None,
        due_mileage: int | None = None,
    ) -> Reminder:
        parsed = self.validate(title, category, due_date, due_mileage)
        row = self.get(reminder_id)
        if row.completed_at is not None:
            raise ValueError("Completed reminders are history; create a new reminder.")
        row.title, row.category = title.strip(), parsed
        row.due_date, row.due_mileage = due_date, due_mileage
        row.updated_at = datetime.now(UTC)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def complete(
        self,
        *,
        reminder_id: str,
        next_due_date: date | None = None,
        next_due_mileage: int | None = None,
    ) -> dict[str, Reminder | None]:
        row = self.get(reminder_id)
        if row.completed_at is not None:
            raise ValueError("Reminder is already completed.")
        next_row = None
        if next_due_date is not None or next_due_mileage is not None:
            self.validate(row.title, row.category, next_due_date, next_due_mileage)
            next_row = Reminder(
                vehicle_id=row.vehicle_id,
                title=row.title,
                category=row.category,
                due_date=next_due_date,
                due_mileage=next_due_mileage,
                previous_id=row.id,
            )
        try:
            completed = datetime.now(UTC)
            changed = self.session.execute(
                update(Reminder)
                .where(col(Reminder.id) == row.id, col(Reminder.completed_at).is_(None))
                .values(completed_at=completed, updated_at=completed)
            )
            if getattr(changed, "rowcount", 0) != 1:
                raise ValueError("Reminder is already completed.")
            if next_row is not None:
                self.session.add(next_row)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(row)
        if next_row is not None:
            self.session.refresh(next_row)
        return {"completed": row, "next": next_row}

    def delete(self, reminder_id: str) -> Reminder:
        row = self.get(reminder_id)
        self.session.delete(row)
        self.session.commit()
        return row

    def reading(self, vehicle: Vehicle, today: date) -> dict[str, Any]:
        # One bounded query per source; date then ID chooses provenance, not maximum miles.
        fuel = self.session.exec(
            select(FuelLog)
            .where(FuelLog.vehicle_id == vehicle.id)
            .order_by(col(FuelLog.date).desc(), col(FuelLog.id).desc())
            .limit(1)
        ).first()
        expense = self.session.exec(
            select(Expense)
            .where(Expense.vehicle_id == vehicle.id, col(Expense.odometer_miles).is_not(None))
            .order_by(col(Expense.date).desc(), col(Expense.id).desc())
            .limit(1)
        ).first()
        candidates = [
            (r.date, r.id, source, r.odometer_miles)
            for r, source in [(fuel, "fuel"), (expense, "expense")]
            if r is not None
        ]
        if not candidates:
            return {
                "miles": vehicle.initial_mileage,
                "date": None,
                "source": "baseline",
                "stale": False,
                "message": (
                    "Mileage status unknown — add a dated reading. "
                    "Initial mileage is baseline only."
                ),
            }
        observed, _, source, miles = max(candidates)
        stale = (today - observed).days > 90
        return {
            "miles": miles,
            "date": observed,
            "source": source,
            "stale": stale,
            "message": "Mileage may be out of date; status may lag."
            if stale
            else "Latest recorded mileage.",
        }

    def list(
        self,
        *,
        vehicle_identifier: str | None = None,
        include_inactive: bool = False,
        today: date | None = None,
    ) -> list[dict[str, Any]]:
        today = today or date.today()
        query = select(Reminder, Vehicle).join(Vehicle, col(Reminder.vehicle_id) == col(Vehicle.id))
        if vehicle_identifier:
            vehicle = VehicleService(self.session).get_vehicle(vehicle_identifier)
            query = query.where(Vehicle.id == vehicle.id)
        if not include_inactive:
            query = query.where(Vehicle.status == VehicleStatus.ACTIVE)
        readings: dict[str, dict[str, Any]] = {}
        result = []
        for row, vehicle in self.session.exec(
            query.order_by(col(Reminder.created_at), col(Reminder.id))
        ):
            if vehicle.id not in readings:
                readings[vehicle.id] = self.reading(vehicle, today)
            reading = readings[vehicle.id]
            miles = reading["miles"] if reading["date"] is not None else None
            if row.completed_at is not None:
                status = "completed"
            elif (row.due_date is not None and row.due_date <= today) or (
                row.due_mileage is not None and miles is not None and miles >= row.due_mileage
            ):
                status = "due"
            elif (row.due_date is not None and (row.due_date - today).days <= 30) or (
                row.due_mileage is not None
                and miles is not None
                and row.due_mileage - miles <= 1000
            ):
                status = "upcoming"
            elif row.due_mileage is not None and (miles is None or reading["stale"]):
                status = "unknown"
            else:
                status = "later"
            result.append(
                {
                    "reminder": row,
                    "registration": vehicle.registration,
                    "vehicle_status": vehicle.status,
                    "status": status,
                    "reading": reading,
                }
            )
        return result
