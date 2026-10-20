"""Fuel log service."""

from datetime import UTC, date, datetime

from pydantic import ValidationError
from sqlmodel import Session

from odometer.models.fuel import FuelLog
from odometer.models.vehicle import Vehicle
from odometer.repositories.fuel_repository import FuelRepository
from odometer.services.exceptions import FuelLogNotFoundError, InvalidFuelLogError
from odometer.services.vehicle_service import VehicleService


class FuelService:
    """Business logic for fuel logs."""

    def __init__(self, session: Session) -> None:
        """Create repository dependencies for fuel operations."""
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

    def update_fuel_log(self, fuel_log_id: str, **changes: object) -> FuelLog:
        """Validate a detached candidate before updating the existing record atomically."""
        current = self.repository.get_by_id(fuel_log_id)
        if current is None:
            raise FuelLogNotFoundError(f"Fuel log not found: {fuel_log_id}.")
        allowed = {
            "date_",
            "odometer_miles",
            "litres",
            "total_cost_pence",
            "station",
            "notes",
            "is_full_tank",
            "price_per_litre_pence",
        }
        if not changes or changes.keys() - allowed:
            raise InvalidFuelLogError("Supply editable fuel fields only.")
        values = current.model_dump()
        values.update({"date" if k == "date_" else k: v for k, v in changes.items()})
        if "price_per_litre_pence" not in changes and (
            values["litres"] != current.litres
            or values["total_cost_pence"] != current.total_cost_pence
        ):
            values["price_per_litre_pence"] = None
        try:
            candidate = FuelLog.model_validate(values, strict=True)
        except ValidationError as exc:
            raise InvalidFuelLogError(str(exc)) from exc
        vehicle = self.vehicle_service.get_vehicle(current.vehicle_id)
        history = self.repository.list(vehicle_id=current.vehicle_id, limit=None)
        self.validate_candidate_history(
            vehicle, [candidate if row.id == current.id else row for row in history]
        )
        if candidate.price_per_litre_pence is None:
            candidate.price_per_litre_pence = candidate.total_cost_pence / candidate.litres
        for key in allowed - {"date_"}:
            setattr(current, key, getattr(candidate, key))
        current.date = candidate.date
        current.updated_at = datetime.now(UTC)
        return self.repository.add(current)

    @staticmethod
    def validate_candidate_history(vehicle: Vehicle, history: list[FuelLog]) -> None:
        """Validate a complete vehicle history without writes (also usable by atomic imports).

        Fills are ordered by date then ID; mileage must never decrease.
        Callers supply all existing plus proposed records.
        """
        from odometer.services.history_validation import validate_fuel_history

        validate_fuel_history(vehicle, history)

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

    def delete_fuel_log(self, fuel_log_id: str) -> FuelLog:
        """Delete a fuel log by id."""
        fuel_log = self.repository.get_by_id(fuel_log_id)
        if fuel_log is None:
            raise FuelLogNotFoundError(f"Fuel log not found: {fuel_log_id}.")
        self.repository.delete(fuel_log)
        return fuel_log
