"""Vehicle service tests."""

from datetime import date

import pytest
from sqlmodel import Session

from odometer.models.enums import VehicleStatus
from odometer.services.exceptions import DuplicateActiveVehicleError, VehicleNotFoundError
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.vehicle_service import VehicleService


def test_create_list_and_normalise_vehicle(session: Session) -> None:
    """Verify vehicle creation normalises registration and appears in active lists."""
    service = VehicleService(session)
    vehicle = service.create_vehicle(
        registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=55
    )

    assert vehicle.registration == "AB12 CDE"
    assert vehicle.normalised_registration == "AB12CDE"
    assert vehicle.fuel_tank_litres == 55
    assert service.list_vehicles() == [vehicle]


def test_set_fuel_tank_capacity(session: Session) -> None:
    """Verify the fuel tank capacity can be added after vehicle creation."""
    service = VehicleService(session)
    vehicle = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)

    updated = service.set_fuel_tank_capacity(vehicle.id, 55)

    assert updated.fuel_tank_litres == 55


def test_reject_invalid_fuel_tank_capacity(session: Session) -> None:
    """Verify zero fuel tank capacity is rejected on create and update."""
    service = VehicleService(session)

    with pytest.raises(ValueError, match="Fuel tank size"):
        service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000, fuel_tank_litres=0)

    vehicle = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)
    with pytest.raises(ValueError, match="Fuel tank size"):
        service.set_fuel_tank_capacity(vehicle.id, 0)


def test_reject_negative_initial_mileage(session: Session) -> None:
    """Verify vehicle creation rejects negative starting mileage."""
    service = VehicleService(session)

    with pytest.raises(ValueError, match="Initial mileage"):
        service.create_vehicle(registration="AB12 CDE", initial_mileage=-1)


def test_prevent_duplicate_active_registration(session: Session) -> None:
    """Verify duplicate active registrations are rejected after normalisation."""
    service = VehicleService(session)
    service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)

    with pytest.raises(DuplicateActiveVehicleError):
        service.create_vehicle(registration="ab12cde", initial_mileage=43_000)


def test_allow_historical_registration_after_archive_or_sold(session: Session) -> None:
    """Verify inactive vehicles do not block reusing a registration."""
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
    """Verify vehicles can move to archived and sold lifecycle states."""
    service = VehicleService(session)
    vehicle = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)

    archived = service.archive_vehicle(vehicle.id)
    assert archived.status == VehicleStatus.ARCHIVED

    replacement = service.create_vehicle(registration="AB12 CDE", initial_mileage=43_000)
    sold = service.mark_vehicle_sold(replacement.id)
    assert sold.status == VehicleStatus.SOLD


def test_vehicle_lookup_handles_historical_missing_and_inactive(session: Session) -> None:
    """Verify vehicle lookup resolves historical rows and active lookup rejects inactive rows."""
    service = VehicleService(session)
    vehicle = service.create_vehicle(registration="AB12 CDE", initial_mileage=42_000)

    assert service.get_active_vehicle(vehicle.id).id == vehicle.id

    sold = service.mark_vehicle_sold(vehicle.id)

    assert service.get_vehicle("AB12CDE").id == sold.id
    with pytest.raises(VehicleNotFoundError, match="No active vehicle"):
        service.get_active_vehicle(sold.id)
    with pytest.raises(VehicleNotFoundError, match="Vehicle not found"):
        service.get_vehicle("ZZ99 ZZZ")


def test_delete_vehicle_cascades_associated_data(session: Session) -> None:
    """Verify vehicle deletion removes associated expenses and fuel logs."""
    vehicles = VehicleService(session)
    vehicle = vehicles.create_vehicle(
        registration="AB12 CDE",
        initial_mileage=42_000,
        fuel_tank_litres=55,
    )
    expenses = ExpenseService(session)
    fuel = FuelService(session)
    expenses.add_expense(
        vehicle_identifier=vehicle.id,
        category="service",
        amount_pence=24_999,
        date_=date(2026, 1, 10),
    )
    fuel.add_fuel_log(
        vehicle_identifier=vehicle.id,
        litres=45.2,
        total_cost_pence=6_850,
        odometer_miles=43_420,
        date_=date(2026, 1, 12),
    )

    result = vehicles.delete_vehicle(vehicle.id)

    assert result.registration == "AB12 CDE"
    assert result.expense_count == 1
    assert result.fuel_log_count == 1
    assert vehicles.list_vehicles(include_inactive=True) == []
    assert expenses.list_expenses() == []
    assert fuel.list_fuel_logs() == []
