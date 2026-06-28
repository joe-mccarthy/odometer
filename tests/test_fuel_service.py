"""Fuel service tests."""

from datetime import date

import pytest
from sqlmodel import Session

from odometer.services.exceptions import InvalidFuelLogError
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService


def test_add_fuel_log_and_calculate_price_per_litre(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=55
    )
    fuel_log = FuelService(session).add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=45.2,
        total_cost_pence=6_850,
        odometer_miles=43_420,
        date_=date(2026, 1, 12),
        station="Tesco",
    )

    assert fuel_log.price_per_litre_pence == pytest.approx(151.548, rel=0.001)


def test_reject_invalid_fuel_values(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=55
    )
    service = FuelService(session)

    with pytest.raises(InvalidFuelLogError):
        service.add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=0,
            total_cost_pence=6_850,
            odometer_miles=43_420,
            date_=date(2026, 1, 12),
        )

    with pytest.raises(InvalidFuelLogError):
        service.add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=45.2,
            total_cost_pence=0,
            odometer_miles=43_420,
            date_=date(2026, 1, 12),
        )

    with pytest.raises(InvalidFuelLogError):
        service.add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=45.2,
            total_cost_pence=6_850,
            odometer_miles=41_999,
            date_=date(2026, 1, 12),
        )


def test_reject_backwards_fuel_mileage_and_list_sorted(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=55
    )
    service = FuelService(session)
    first = service.add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=45.2,
        total_cost_pence=6_850,
        odometer_miles=43_420,
        date_=date(2026, 1, 12),
    )
    second = service.add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=43.0,
        total_cost_pence=6_600,
        odometer_miles=44_000,
        date_=date(2026, 1, 20),
    )

    assert service.list_fuel_logs(vehicle_identifier=vehicle.id) == [second, first]

    with pytest.raises(InvalidFuelLogError):
        service.add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=20,
            total_cost_pence=3_000,
            odometer_miles=43_900,
            date_=date(2026, 1, 21),
        )


def test_reject_fuel_log_without_tank_size(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000
    )

    with pytest.raises(InvalidFuelLogError, match="Fuel tank size must be set"):
        FuelService(session).add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=45.2,
            total_cost_pence=6_850,
            odometer_miles=43_420,
            date_=date(2026, 1, 12),
        )


def test_add_fuel_log_can_set_tank_size(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000
    )

    fuel_log = FuelService(session).add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=45.2,
        total_cost_pence=6_850,
        odometer_miles=43_420,
        date_=date(2026, 1, 12),
        fuel_tank_litres=55,
    )

    updated_vehicle = VehicleService(session).get_vehicle(vehicle.id)
    assert updated_vehicle.fuel_tank_litres == 55
    assert fuel_log.litres == 45.2


def test_reject_fuel_log_over_tank_size(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=40
    )

    with pytest.raises(InvalidFuelLogError, match="cannot exceed"):
        FuelService(session).add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=45.2,
            total_cost_pence=6_850,
            odometer_miles=43_420,
            date_=date(2026, 1, 12),
        )


def test_reject_over_tank_size_without_saving_new_tank_size(session: Session) -> None:
    vehicle = VehicleService(session).create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000
    )

    with pytest.raises(InvalidFuelLogError, match="cannot exceed"):
        FuelService(session).add_fuel_log(
            vehicle_identifier=vehicle.id,
            litres=45.2,
            total_cost_pence=6_850,
            odometer_miles=43_420,
            date_=date(2026, 1, 12),
            fuel_tank_litres=40,
        )

    updated_vehicle = VehicleService(session).get_vehicle(vehicle.id)
    assert updated_vehicle.fuel_tank_litres is None
