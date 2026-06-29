"""Vehicle repository."""

from sqlmodel import Session, col, select

from odometer.models.enums import VehicleStatus
from odometer.models.vehicle import Vehicle


class VehicleRepository:
    """Persistence operations for vehicles."""

    def __init__(self, session: Session) -> None:
        """Store the SQLModel session used by all vehicle queries."""
        self.session = session

    def add(self, vehicle: Vehicle) -> Vehicle:
        """Persist a vehicle."""
        self.session.add(vehicle)
        self.session.commit()
        self.session.refresh(vehicle)
        return vehicle

    def save(self, vehicle: Vehicle) -> Vehicle:
        """Persist updates to a vehicle."""
        self.session.add(vehicle)
        self.session.commit()
        self.session.refresh(vehicle)
        return vehicle

    def delete(self, vehicle: Vehicle, *, commit: bool = True) -> None:
        """Delete a vehicle."""
        self.session.delete(vehicle)
        if commit:
            self.session.commit()

    def get_by_id(self, vehicle_id: str) -> Vehicle | None:
        """Return a vehicle by id."""
        return self.session.get(Vehicle, vehicle_id)

    def get_active_by_registration(self, normalised_registration: str) -> Vehicle | None:
        """Return the active vehicle for a normalised registration."""
        statement = select(Vehicle).where(
            Vehicle.normalised_registration == normalised_registration,
            Vehicle.status == VehicleStatus.ACTIVE,
        )
        return self.session.exec(statement).first()

    def list_by_registration(self, normalised_registration: str) -> list[Vehicle]:
        """Return all vehicles matching a normalised registration."""
        statement = (
            select(Vehicle)
            .where(Vehicle.normalised_registration == normalised_registration)
            .order_by(col(Vehicle.created_at).desc())
        )
        return list(self.session.exec(statement).all())

    def list(self, include_inactive: bool = False) -> list[Vehicle]:
        """Return vehicles, active by default."""
        statement = select(Vehicle)
        if not include_inactive:
            statement = statement.where(Vehicle.status == VehicleStatus.ACTIVE)
        statement = statement.order_by(col(Vehicle.registration), col(Vehicle.created_at))
        return list(self.session.exec(statement).all())
