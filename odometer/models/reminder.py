"""Persisted reminder occurrences; completion retains the original occurrence."""

import datetime as dt
from uuid import uuid4

from sqlmodel import Field, SQLModel

from odometer.models.enums import ExpenseCategory


class Reminder(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    vehicle_id: str = Field(foreign_key="vehicle.id", index=True)
    title: str
    category: ExpenseCategory
    due_date: dt.date | None = None
    due_mileage: int | None = None
    completed_at: dt.datetime | None = None
    previous_id: str | None = None
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
