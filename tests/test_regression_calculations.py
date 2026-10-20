"""Boundary regressions for shared calculations across every presentation layer."""

from datetime import date

import pytest
from sqlmodel import Session

from odometer.models.fuel import FuelLog
from odometer.services.calculation_service import CalculationService
from odometer.services.exceptions import CalculationUnavailableError
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService
from odometer.utils.money import parse_money_to_pence


@pytest.mark.parametrize(
    ("amount", "pence"),
    [("0.10", 10), ("1.005", 101), ("2.675", 268), ("999999.99", 99999999)],
)
def test_money_rounds_half_up_to_integer_pence(amount: str, pence: int) -> None:
    assert parse_money_to_pence(amount) == pence
    assert isinstance(parse_money_to_pence(amount), int)


def test_partial_fills_require_full_baseline_and_closure() -> None:
    logs = [
        FuelLog(
            vehicle_id="test",
            date=date(2026, 1, day),
            odometer_miles=miles,
            litres=litres,
            total_cost_pence=100,
            is_full_tank=full,
        )
        for day, miles, litres, full in [
            (1, 100, 10, False),
            (2, 200, 40, True),
            (3, 300, 10, False),
            (4, 400, 15, False),
            (5, 500, 25, True),
            (6, 700, 20, True),
            (7, 800, 12, False),
        ]
    ]
    with pytest.raises(CalculationUnavailableError):
        CalculationService.mpg_stats_from_logs(logs[:4])
    segments = CalculationService.mpg_segments(reversed(logs))
    assert [(s.miles, s.litres) for s in segments] == [(300, 50), (200, 20)]
    assert segments[0].uk_mpg == pytest.approx(300 * 4.54609 / 50)
    assert segments[1].uk_mpg == pytest.approx(200 * 4.54609 / 20)
    assert segments[1].date == date(2026, 1, 6)


def test_calendar_boundaries_and_prior_reading_baseline(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(registration="AB12CDE", initial_mileage=1000)
    expenses = ExpenseService(session)
    for when, amount, mileage in [
        (date(2023, 12, 31), 101, 1100),
        (date(2024, 1, 1), 202, 1120),
        (date(2024, 1, 31), 303, 1150),
        (date(2024, 2, 29), 404, 1190),
        (date(2024, 3, 1), 505, 1200),
        (date(2025, 1, 1), 606, 1210),
    ]:
        expenses.add_expense(
            vehicle_identifier=vehicle.id,
            category="service",
            amount_pence=amount,
            date_=when,
            odometer_miles=mileage,
        )
    service = CalculationService(session)
    monthly = service.monthly_summaries(vehicle_identifier=vehicle.id, year=2024)
    assert [(m.total_spend_pence, m.miles_driven) for m in monthly[:3]] == [
        (505, 50),
        (404, 40),
        (505, 10),
    ]
    assert monthly[3].total_spend_pence == 0
    assert monthly[3].miles_driven is None
    assert monthly[3].cost_per_mile_pence is None
    assert [
        (a.period, a.total_spend_pence, a.miles_driven)
        for a in service.annual_summaries(vehicle_identifier=vehicle.id)
    ] == [("2023", 101, 100), ("2024", 1414, 100), ("2025", 606, 10)]


def test_fuel_deduplication_is_per_vehicle_and_selected_period(session: Session) -> None:
    vehicles = VehicleService(session)
    first = vehicles.create_vehicle(
        registration="AB12CDE",
        initial_mileage=1000,
        fuel_tank_litres=50,
        purchase_price_pence=100001,
    )
    second = vehicles.create_vehicle(registration="XY12ABC", initial_mileage=2000)
    expenses = ExpenseService(session)
    for vehicle, when, amount in [
        (first, date(2026, 1, 31), 101),
        (first, date(2026, 2, 1), 202),
        (second, date(2026, 2, 1), 303),
    ]:
        expenses.add_expense(
            vehicle_identifier=vehicle.id, category="fuel", amount_pence=amount, date_=when
        )
    expenses.add_expense(
        vehicle_identifier=first.id, category="service", amount_pence=7, date_=date(2026, 2, 1)
    )
    FuelService(session).add_fuel_log(
        vehicle_identifier=first.id,
        litres=10,
        total_cost_pence=404,
        odometer_miles=1010,
        date_=date(2026, 2, 1),
    )
    service = CalculationService(session)
    monthly = service.monthly_summaries(year=2026)
    assert monthly[0].total_spend_pence == 101
    assert monthly[1].total_spend_pence == 714
    assert monthly[1].fuel_spend_pence == 707
    breakdown = service.category_breakdown_for_scope()
    assert sum(item.amount_pence for item in breakdown) == 714
    metrics = service.vehicle_cost_metrics(first.id)[0]
    assert metrics.running_cost_pence == 411
    assert metrics.ownership_cost_pence == 100412
    assert metrics.running_cost_per_mile_pence == 41.1
    assert service.vehicle_cost_metrics(second.id)[0].running_cost_per_mile_pence is None
