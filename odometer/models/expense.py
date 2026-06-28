"""Expense model."""

import datetime as dt
from uuid import uuid4

from sqlmodel import Field, SQLModel

from odometer.models.enums import ExpenseCategory


class Expense(SQLModel, table=True):
    """A non-fuel or manually logged vehicle ownership expense."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    vehicle_id: str = Field(foreign_key="vehicle.id", index=True)
    date: dt.date = Field(index=True)
    category: ExpenseCategory = Field(index=True)
    amount_pence: int
    odometer_miles: int | None = Field(default=None, index=True)
    description: str | None = None
    vendor: str | None = None
    notes: str | None = None
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
