"""Fuel log service."""

from datetime import date

from sqlmodel import Session

from odometer.models.fuel import FuelLog
from odometer.repositories.fuel_repository import FuelRepository
from odometer.services.exceptions import InvalidFuelLogError
from odometer.services.vehicle_service import VehicleService


class FuelService:
    """Business logic for fuel logs."""

    def __init__(self, session: Session) -> None:
        self.repository = FuelRepository(session)
        self.vehicle_service = VehicleService(session)

    def add_fuel_log(
        self,
        *,
        vehicle_identifier: str,
        litres: float,
        total_cost_pence: int,
        odometer_miles: int,
        date_: date,
        station: str | None = None,
        is_full_tank: bool = True,
        notes: str | None = None,
        price_per_litre_pence: float | None = None,
        fuel_tank_litres: float | None = None,
    ) -> FuelLog:
        """Add a fuel log to a vehicle."""
        vehicle = self.vehicle_service.get_vehicle(vehicle_identifier)
        if litres <= 0:
            raise InvalidFuelLogError("Fuel litres must be greater than zero.")
        if total_cost_pence <= 0:
            raise InvalidFuelLogError("Fuel amount must be greater than zero.")
        if odometer_miles < vehicle.initial_mileage:
            raise InvalidFuelLogError("Fuel mileage cannot be lower than initial mileage.")

        latest = self.repository.latest_for_vehicle(vehicle.id)
        if latest is not None and odometer_miles < latest.odometer_miles:
            raise InvalidFuelLogError("Fuel odometer readings cannot go backwards.")

        fuel_tank_capacity = vehicle.fuel_tank_litres
        if fuel_tank_litres is not None:
            if fuel_tank_litres <= 0:
                raise InvalidFuelLogError("Fuel tank size must be greater than zero litres.")
            fuel_tank_capacity = fuel_tank_litres

        if fuel_tank_capacity is None:
            raise InvalidFuelLogError("Fuel tank size must be set before adding fuel logs.")
        if litres > fuel_tank_capacity:
            raise InvalidFuelLogError("Fuel litres cannot exceed the vehicle fuel tank size.")

        if fuel_tank_litres is not None:
            vehicle = self.vehicle_service.set_fuel_tank_capacity(vehicle.id, fuel_tank_litres)

        calculated_price = price_per_litre_pence
        if calculated_price is None:
            calculated_price = total_cost_pence / litres

        fuel_log = FuelLog(
            vehicle_id=vehicle.id,
            date=date_,
            odometer_miles=odometer_miles,
            litres=litres,
            total_cost_pence=total_cost_pence,
            price_per_litre_pence=calculated_price,
            station=station,
            is_full_tank=is_full_tank,
            notes=notes,
        )
        return self.repository.add(fuel_log)

    def list_fuel_logs(
        self,
        *,
        vehicle_identifier: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = 50,
        ascending: bool = False,
    ) -> list[FuelLog]:
        """List fuel logs with optional filters."""
        vehicle_id = None
        if vehicle_identifier is not None:
            vehicle_id = self.vehicle_service.get_vehicle(vehicle_identifier).id
        return self.repository.list(
            vehicle_id=vehicle_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            ascending=ascending,
        )
