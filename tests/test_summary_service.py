"""Summary service tests."""

from datetime import date

from sqlmodel import Session

from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.summary_service import SummaryService
from odometer.services.vehicle_service import VehicleService


def test_overall_summary(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE",
        initial_mileage=42_000,
        fuel_tank_litres=55,
        purchase_price_pence=1_250_000,
    )
    ExpenseService(session).add_expense(
        vehicle_identifier=vehicle.id,
        category="service",
        amount_pence=24_999,
        date_=date(2026, 1, 10),
        odometer_miles=43_000,
    )
    FuelService(session).add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=45.2,
        total_cost_pence=6_850,
        odometer_miles=43_420,
        date_=date(2026, 1, 12),
    )

    summary = SummaryService(session).overall_summary(vehicle_identifier=vehicle.id)

    assert summary.total_spend_pence == 31_849
    assert summary.fuel_spend_pence == 6_850
    assert summary.non_fuel_spend_pence == 24_999
    assert summary.expense_count == 1
    assert summary.fuel_log_count == 1
    assert summary.miles_driven == 1_420
    assert summary.running_cost_per_mile_pence == 31_849 / 1_420
