"""Strict transport schemas, independent of business rules."""

from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationInfo,
    field_validator,
    model_validator,
)

from odometer.models.enums import ExpenseCategory

Integer = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]
PositiveInteger = Annotated[int, Field(strict=True, gt=0, le=9007199254740991)]
PositiveNumber = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Year = Annotated[int, Field(strict=True, ge=1, le=9998)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def iso_dates(cls, value: Any, info: ValidationInfo) -> Any:
        if (
            info.field_name in {"date", "purchase_date", "due_date", "next_due_date"}
            and value is not None
        ):
            if not isinstance(value, str):
                raise ValueError("Use YYYY-MM-DD")
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError as exception:
                raise ValueError("Use YYYY-MM-DD") from exception
        return value


class VehicleCreate(Body):
    registration: Annotated[StrictStr, Field(min_length=1)]
    initial_mileage: Integer
    make: StrictStr | None = None
    model: StrictStr | None = None
    nickname: StrictStr | None = None
    year: Year | None = None
    fuel_tank_litres: PositiveNumber | None = None
    purchase_date: date | None = None
    purchase_price_pence: Integer | None = None

    @model_validator(mode="after")
    def nonblank(self) -> Self:
        if not self.registration.strip():
            raise ValueError("Registration must not be blank")
        return self


class VehiclePatch(Body):
    status: Literal["SOLD", "ARCHIVED"] | None = None
    fuel_tank_litres: PositiveNumber | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        if len(self.model_fields_set) != 1 or all(
            value is None for value in (self.status, self.fuel_tank_litres)
        ):
            raise ValueError("Supply exactly one status or fuel_tank_litres")
        return self


class FuelCreate(Body):
    date: date
    odometer_miles: Integer
    litres: PositiveNumber
    total_cost_pence: PositiveInteger
    station: StrictStr | None = None
    notes: StrictStr | None = None
    is_full_tank: StrictBool = True
    price_per_litre_pence: PositiveNumber | None = None
    fuel_tank_litres: PositiveNumber | None = None


class ExpenseCreate(Body):
    date: date
    category: ExpenseCategory
    amount_pence: PositiveInteger
    odometer_miles: Integer | None = None
    description: StrictStr | None = None
    vendor: StrictStr | None = None
    notes: StrictStr | None = None


class ReminderInput(Body):
    title: StrictStr
    category: ExpenseCategory
    due_date: date | None = None
    due_mileage: Integer | None = None


class ReminderComplete(Body):
    next_due_date: date | None = None
    next_due_mileage: Integer | None = None


class FuelUpdate(FuelCreate):
    """Complete editable record; vehicle tank capacity is a separate operation."""

    @model_validator(mode="after")
    def no_capacity_change(self) -> Self:
        if "fuel_tank_litres" in self.model_fields_set:
            raise ValueError("Change tank capacity using the vehicle controls")
        return self
