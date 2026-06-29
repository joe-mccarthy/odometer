"""Expense repository."""

from datetime import date

from sqlmodel import Session, col, select

from odometer.models.enums import ExpenseCategory
from odometer.models.expense import Expense


class ExpenseRepository:
    """Persistence operations for expenses."""

    def __init__(self, session: Session) -> None:
        """Store the SQLModel session used by all expense queries."""
        self.session = session

    def add(self, expense: Expense) -> Expense:
        """Persist an expense."""
        self.session.add(expense)
        self.session.commit()
        self.session.refresh(expense)
        return expense

    def get_by_id(self, expense_id: str) -> Expense | None:
        """Return an expense by id."""
        return self.session.get(Expense, expense_id)

    def list(
        self,
        *,
        vehicle_id: str | None = None,
        category: ExpenseCategory | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = 50,
        ascending: bool = False,
    ) -> list[Expense]:
        """Return expenses matching optional filters."""
        statement = select(Expense)
        if vehicle_id is not None:
            statement = statement.where(Expense.vehicle_id == vehicle_id)
        if category is not None:
            statement = statement.where(Expense.category == category)
        if date_from is not None:
            statement = statement.where(Expense.date >= date_from)
        if date_to is not None:
            statement = statement.where(Expense.date <= date_to)

        if ascending:
            statement = statement.order_by(
                col(Expense.date), col(Expense.odometer_miles), col(Expense.created_at)
            )
        else:
            statement = statement.order_by(
                col(Expense.date).desc(),
                col(Expense.odometer_miles).desc(),
                col(Expense.created_at).desc(),
            )
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def delete(self, expense: Expense, *, commit: bool = True) -> None:
        """Delete an expense."""
        self.session.delete(expense)
        if commit:
            self.session.commit()

    def delete_for_vehicle(self, vehicle_id: str, *, commit: bool = True) -> int:
        """Delete all expenses for a vehicle and return the count."""
        expenses = self.list(vehicle_id=vehicle_id, limit=None)
        for expense in expenses:
            self.session.delete(expense)
        if commit:
            self.session.commit()
        return len(expenses)
