"""Calculation service tests."""

from datetime import date

import pytest
from sqlmodel import Session

from odometer.models.enums import ExpenseCategory
from odometer.services.calculation_service import CalculationService
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService


def test_costs_mpg_breakdowns_and_period_summaries(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE",
        initial_mileage=10_000,
        fuel_tank_litres=55,
        purchase_price_pence=1_000_000,
    )
    expenses = ExpenseService(session)
    fuel = FuelService(session)

    expenses.add_expense(
        vehicle_identifier=vehicle.id,
        category="service",
        amount_pence=20_000,
        date_=date(2026, 1, 3),
        odometer_miles=10_050,
    )
    expenses.add_expense(
        vehicle_identifier=vehicle.id,
        category="fuel",
        amount_pence=5_000,
        date_=date(2026, 1, 4),
        odometer_miles=10_060,
    )
    fuel.add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=40,
        total_cost_pence=6_000,
        odometer_miles=10_100,
        date_=date(2026, 1, 5),
        is_full_tank=True,
    )
    fuel.add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=20,
        total_cost_pence=3_000,
        odometer_miles=10_200,
        date_=date(2026, 2, 5),
        is_full_tank=False,
    )
    fuel.add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=45,
        total_cost_pence=7_000,
        odometer_miles=10_400,
        date_=date(2026, 3, 5),
        is_full_tank=True,
    )

    service = CalculationService(session)
    metrics = service.vehicle_cost_metrics(vehicle.id)[0]
    assert metrics.miles_driven == 400
    assert metrics.running_cost_pence == 36_000
    assert metrics.ownership_cost_pence == 1_036_000
    assert metrics.running_cost_per_mile_pence == 90
    assert metrics.ownership_cost_per_mile_pence == 2_590

    mpg = service.mpg_stats(vehicle.id)
    assert mpg.segment_count == 1
    assert mpg.latest_mpg == pytest.approx(300 / (45 / 4.54609))

    breakdown = service.category_breakdown_for_scope(vehicle_identifier=vehicle.id)
    assert breakdown[0].category == ExpenseCategory.SERVICE
    assert breakdown[0].amount_pence == 20_000
    assert breakdown[1].category == ExpenseCategory.FUEL
    assert breakdown[1].amount_pence == 16_000

    monthly = service.monthly_summaries(vehicle_identifier=vehicle.id, year=2026)
    assert monthly[0].period == "2026-01"
    assert monthly[0].total_spend_pence == 26_000
    assert monthly[0].fuel_spend_pence == 6_000
    assert monthly[0].miles_driven == 100

    annual = service.annual_summaries(vehicle_identifier=vehicle.id)
    assert annual[0].period == "2026"
    assert annual[0].total_spend_pence == 36_000

    rolling = service.rolling_averages(vehicle_identifier=vehicle.id)
    assert rolling.all_months_average_pence == 12_000
    assert rolling.last_3_months_average_pence == 12_000
