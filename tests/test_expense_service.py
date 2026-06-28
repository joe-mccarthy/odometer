"""Expense service tests."""

from datetime import date

import pytest
from sqlmodel import Session

from odometer.models.enums import ExpenseCategory
from odometer.services.exceptions import InvalidExpenseError
from odometer.services.expense_service import ExpenseService
from odometer.services.vehicle_service import VehicleService


def test_add_and_list_expenses(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000
    )
    service = ExpenseService(session)

    expense = service.add_expense(
        vehicle_identifier=vehicle.id,
        category="service",
        amount_pence=24_999,
        date_=date(2026, 1, 10),
        odometer_miles=43_000,
        description="Annual service",
    )

    assert expense.category == ExpenseCategory.SERVICE
    assert service.list_expenses(vehicle_identifier="AB12CDE") == [expense]
    assert service.list_expenses(category=ExpenseCategory.SERVICE) == [expense]
    assert service.list_expenses(category=ExpenseCategory.MOT) == []


def test_add_fine_expense(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000
    )
    service = ExpenseService(session)

    expense = service.add_expense(
        vehicle_identifier=vehicle.id,
        category="fine",
        amount_pence=6_500,
        date_=date(2026, 1, 10),
        description="Parking fine",
    )

    assert expense.category == ExpenseCategory.FINE


def test_reject_invalid_expense_amount(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000
    )

    with pytest.raises(InvalidExpenseError):
        ExpenseService(session).add_expense(
            vehicle_identifier=vehicle.id,
            category="service",
            amount_pence=0,
            date_=date(2026, 1, 10),
        )


def test_reject_expense_mileage_below_initial(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000
    )

    with pytest.raises(InvalidExpenseError):
        ExpenseService(session).add_expense(
            vehicle_identifier=vehicle.id,
            category="service",
            amount_pence=10_000,
            date_=date(2026, 1, 10),
            odometer_miles=41_999,
        )
