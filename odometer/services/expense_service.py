"""Expense service."""

from datetime import UTC, date, datetime

from pydantic import ValidationError
from sqlmodel import Session

from odometer.models.enums import ExpenseCategory
from odometer.models.expense import Expense
from odometer.repositories.expense_repository import ExpenseRepository
from odometer.services.exceptions import ExpenseNotFoundError, InvalidExpenseError
from odometer.services.history_validation import validate_expense
from odometer.services.vehicle_service import VehicleService


class ExpenseService:
    """Business logic for expenses."""

    def __init__(self, session: Session) -> None:
        """Create repository dependencies for expense operations."""
        self.repository = ExpenseRepository(session)
        self.vehicle_service = VehicleService(session)

    def add_expense(
        self,
        *,
        vehicle_identifier: str,
        category: ExpenseCategory | str,
        amount_pence: int,
        date_: date,
        odometer_miles: int | None = None,
        description: str | None = None,
        vendor: str | None = None,
        notes: str | None = None,
    ) -> Expense:
        """Add an expense to a vehicle."""
        vehicle = self.vehicle_service.get_vehicle(vehicle_identifier)
        parsed_category = self._parse_category(category)

        if amount_pence <= 0:
            raise InvalidExpenseError("Expense amount must be greater than zero.")
        if odometer_miles is not None and odometer_miles < vehicle.initial_mileage:
            raise InvalidExpenseError("Expense mileage cannot be lower than initial mileage.")

        expense = Expense(
            vehicle_id=vehicle.id,
            date=date_,
            category=parsed_category,
            amount_pence=amount_pence,
            odometer_miles=odometer_miles,
            description=description,
            vendor=vendor,
            notes=notes,
        )
        return self.repository.add(expense)

    def update_expense(self, expense_id: str, **changes: object) -> Expense:
        """Validate a detached correction and preserve identity and vehicle."""
        current = self.repository.get_by_id(expense_id)
        if current is None:
            raise ExpenseNotFoundError(f"Expense not found: {expense_id}.")
        allowed = {
            "date_",
            "category",
            "amount_pence",
            "odometer_miles",
            "description",
            "vendor",
            "notes",
        }
        if not changes or changes.keys() - allowed:
            raise InvalidExpenseError("Supply editable expense fields only.")
        values = current.model_dump()
        values.update({"date" if k == "date_" else k: v for k, v in changes.items()})
        values["category"] = self._parse_category(values["category"])
        try:
            candidate = Expense.model_validate(values, strict=True)
        except ValidationError as exc:
            raise InvalidExpenseError(str(exc)) from exc
        vehicle = self.vehicle_service.get_vehicle(current.vehicle_id)
        validate_expense(vehicle, candidate)
        for key in allowed - {"date_"}:
            setattr(current, key, getattr(candidate, key))
        current.date = candidate.date
        current.updated_at = datetime.now(UTC)
        return self.repository.add(current)

    def list_expenses(
        self,
        *,
        vehicle_identifier: str | None = None,
        category: ExpenseCategory | str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = 50,
        ascending: bool = False,
        offset: int = 0,
    ) -> list[Expense]:
        """List expenses with optional filters."""
        vehicle_id = None
        if vehicle_identifier is not None:
            vehicle_id = self.vehicle_service.get_vehicle(vehicle_identifier).id
        parsed_category = self._parse_category(category) if category is not None else None
        return self.repository.list(
            vehicle_id=vehicle_id,
            category=parsed_category,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            ascending=ascending,
            offset=offset,
        )

    def delete_expense(self, expense_id: str) -> Expense:
        """Delete an expense by id."""
        expense = self.repository.get_by_id(expense_id)
        if expense is None:
            raise ExpenseNotFoundError(f"Expense not found: {expense_id}.")
        self.repository.delete(expense)
        return expense

    @staticmethod
    def _parse_category(category: object) -> ExpenseCategory:
        """Convert enum or user-entered category text into `ExpenseCategory`."""
        if isinstance(category, ExpenseCategory):
            return category
        if not isinstance(category, str) or not category.strip():
            raise InvalidExpenseError("Expense category is required; choose a valid category.")
        try:
            return ExpenseCategory.from_input(category)
        except ValueError as exc:
            raise InvalidExpenseError(f"Unknown expense category: {category}.") from exc
