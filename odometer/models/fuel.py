"""Fuel log model."""

import datetime as dt
from uuid import uuid4

from sqlmodel import Field, SQLModel


class FuelLog(SQLModel, table=True):
    """A fuel fill-up for a tracked vehicle."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    vehicle_id: str = Field(foreign_key="vehicle.id", index=True)
    date: dt.date = Field(index=True)
    odometer_miles: int = Field(index=True)
    litres: float
    total_cost_pence: int
    price_per_litre_pence: float | None = None
    station: str | None = None
    is_full_tank: bool = True
    notes: str | None = None
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
