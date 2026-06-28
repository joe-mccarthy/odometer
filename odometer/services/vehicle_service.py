"""Vehicle service."""

from datetime import UTC, date, datetime

from sqlmodel import Session

from odometer.models.enums import VehicleStatus
from odometer.models.vehicle import Vehicle
from odometer.repositories.vehicle_repository import VehicleRepository
from odometer.services.exceptions import DuplicateActiveVehicleError, VehicleNotFoundError
from odometer.utils.registration import normalise_registration


class VehicleService:
    """Business logic for vehicles."""

    def __init__(self, session: Session) -> None:
        self.repository = VehicleRepository(session)

    def create_vehicle(
        self,
        *,
        registration: str,
        initial_mileage: int,
        make: str | None = None,
        model: str | None = None,
        nickname: str | None = None,
        year: int | None = None,
        fuel_tank_litres: float | None = None,
        purchase_date: date | None = None,
        purchase_price_pence: int | None = None,
    ) -> Vehicle:
        """Create a new active vehicle."""
        if initial_mileage < 0:
            raise ValueError("Initial mileage must be zero or greater.")
        if fuel_tank_litres is not None and fuel_tank_litres <= 0:
            raise ValueError("Fuel tank size must be greater than zero litres.")

        normalised = normalise_registration(registration)
        if self.repository.get_active_by_registration(normalised) is not None:
            raise DuplicateActiveVehicleError(
                f"An active vehicle already exists for registration {normalised}."
            )

        vehicle = Vehicle(
            registration=registration.strip().upper(),
            normalised_registration=normalised,
            make=make,
            model=model,
            nickname=nickname,
            year=year,
            initial_mileage=initial_mileage,
            fuel_tank_litres=fuel_tank_litres,
            purchase_date=purchase_date,
            purchase_price_pence=purchase_price_pence,
        )
        return self.repository.add(vehicle)

    def list_vehicles(self, include_inactive: bool = False) -> list[Vehicle]:
        """List vehicles."""
        return self.repository.list(include_inactive=include_inactive)

    def get_vehicle(self, identifier: str) -> Vehicle:
        """Resolve a vehicle by id or registration."""
        vehicle = self.repository.get_by_id(identifier)
        if vehicle is not None:
            return vehicle

        normalised = normalise_registration(identifier)
        vehicle = self.repository.get_active_by_registration(normalised)
        if vehicle is not None:
            return vehicle

        historical = self.repository.list_by_registration(normalised)
        if historical:
            return historical[0]

        raise VehicleNotFoundError(f"Vehicle not found: {identifier}.")

    def get_active_vehicle(self, identifier: str) -> Vehicle:
        """Resolve an active vehicle by id or registration."""
        vehicle = self.get_vehicle(identifier)
        if vehicle.status != VehicleStatus.ACTIVE:
            raise VehicleNotFoundError(f"No active vehicle found for {identifier}.")
        return vehicle

    def set_fuel_tank_capacity(self, identifier: str, fuel_tank_litres: float) -> Vehicle:
        """Set a vehicle fuel tank capacity."""
        if fuel_tank_litres <= 0:
            raise ValueError("Fuel tank size must be greater than zero litres.")

        vehicle = self.get_vehicle(identifier)
        vehicle.fuel_tank_litres = fuel_tank_litres
        vehicle.updated_at = datetime.now(UTC)
        return self.repository.save(vehicle)

    def archive_vehicle(self, identifier: str) -> Vehicle:
        """Mark a vehicle as archived."""
        vehicle = self.get_vehicle(identifier)
        vehicle.status = VehicleStatus.ARCHIVED
        vehicle.updated_at = datetime.now(UTC)
        return self.repository.save(vehicle)

    def mark_vehicle_sold(self, identifier: str) -> Vehicle:
        """Mark a vehicle as sold."""
        vehicle = self.get_vehicle(identifier)
        vehicle.status = VehicleStatus.SOLD
        vehicle.updated_at = datetime.now(UTC)
        return self.repository.save(vehicle)
