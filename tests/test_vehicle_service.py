"""Vehicle service tests."""

import pytest
from sqlmodel import Session

from odometer.models.enums import VehicleStatus
from odometer.services.exceptions import DuplicateActiveVehicleError
from odometer.services.vehicle_service import VehicleService


def test_create_list_and_normalise_vehicle(session: Session) -> None:
    service = VehicleService(session)
    vehicle = service.create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=55
    )

    assert vehicle.registration == "AB12 CDE"
    assert vehicle.normalised_registration == "AB12CDE"
    assert vehicle.fuel_tank_litres == 55
    assert service.list_vehicles() == [vehicle]


def test_set_fuel_tank_capacity(session: Session) -> None:
    service = VehicleService(session)
    vehicle = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)

    updated = service.set_fuel_tank_capacity(vehicle.id, 55)

    assert updated.fuel_tank_litres == 55


def test_reject_invalid_fuel_tank_capacity(session: Session) -> None:
    service = VehicleService(session)

    with pytest.raises(ValueError, match="Fuel tank size"):
        service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=0)

    vehicle = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)
    with pytest.raises(ValueError, match="Fuel tank size"):
        service.set_fuel_tank_capacity(vehicle.id, 0)


def test_prevent_duplicate_active_registration(session: Session) -> None:
    service = VehicleService(session)
    service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)

    with pytest.raises(DuplicateActiveVehicleError):
        service.create_vehicle(registration="ab12cde", initial_mileage=43_000)


def test_allow_historical_registration_after_archive_or_sold(session: Session) -> None:
    service = VehicleService(session)
    first = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)
    archived = service.archive_vehicle(first.id)
    second = service.create_vehicle(registration="AB12 CDE", initial_mileage=50_000)
    sold = service.mark_vehicle_sold(second.id)
    third = service.create_vehicle(registration="AB12 CDE", initial_mileage=60_000)

    assert archived.status == VehicleStatus.ARCHIVED
    assert sold.status == VehicleStatus.SOLD
    assert third.status == VehicleStatus.ACTIVE
    assert len(service.list_vehicles(include_inactive=True)) == 3


def test_archive_and_mark_sold(session: Session) -> None:
    service = VehicleService(session)
    vehicle = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)

    archived = service.archive_vehicle(vehicle.id)
    assert archived.status == VehicleStatus.ARCHIVED

    replacement = service.create_vehicle(registration="AB12 CDE", initial_mileage=43_000)
    sold = service.mark_vehicle_sold(replacement.id)
    assert sold.status == VehicleStatus.SOLD
