"""Vehicle model."""

import datetime as dt
from uuid import uuid4

from sqlmodel import Field, SQLModel

from odometer.models.enums import VehicleStatus


class Vehicle(SQLModel, table=True):
    """A vehicle tracked by Odometer."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    registration: str = Field(index=True)
    normalised_registration: str = Field(index=True)
    make: str | None = None
    model: str | None = None
    nickname: str | None = None
    year: int | None = None
    initial_mileage: int
    fuel_tank_litres: float | None = None
    purchase_date: dt.date | None = None
    purchase_price_pence: int | None = None
    status: VehicleStatus = Field(default=VehicleStatus.ACTIVE, index=True)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
