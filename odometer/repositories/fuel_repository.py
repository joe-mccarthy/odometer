"""Fuel log repository."""

from datetime import date

from sqlmodel import Session, col, select

from odometer.models.fuel import FuelLog


class FuelRepository:
    """Persistence operations for fuel logs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, fuel_log: FuelLog) -> FuelLog:
        """Persist a fuel log."""
        self.session.add(fuel_log)
        self.session.commit()
        self.session.refresh(fuel_log)
        return fuel_log

    def list(
        self,
        *,
        vehicle_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = 50,
        ascending: bool = False,
    ) -> list[FuelLog]:
        """Return fuel logs matching optional filters."""
        statement = select(FuelLog)
        if vehicle_id is not None:
            statement = statement.where(FuelLog.vehicle_id == vehicle_id)
        if date_from is not None:
            statement = statement.where(FuelLog.date >= date_from)
        if date_to is not None:
            statement = statement.where(FuelLog.date <= date_to)

        if ascending:
            statement = statement.order_by(
                col(FuelLog.odometer_miles), col(FuelLog.date), col(FuelLog.created_at)
            )
        else:
            statement = statement.order_by(
                col(FuelLog.date).desc(),
                col(FuelLog.odometer_miles).desc(),
                col(FuelLog.created_at).desc(),
            )
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def latest_for_vehicle(self, vehicle_id: str) -> FuelLog | None:
        """Return the latest fuel log by odometer reading."""
        statement = (
            select(FuelLog)
            .where(FuelLog.vehicle_id == vehicle_id)
            .order_by(
                col(FuelLog.odometer_miles).desc(),
                col(FuelLog.date).desc(),
                col(FuelLog.created_at).desc(),
            )
        )
        return self.session.exec(statement).first()
