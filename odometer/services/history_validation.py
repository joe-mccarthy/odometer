"""Pure candidate validation shared by corrections and atomic imports."""

import math
from datetime import date

from odometer.models.fuel import FuelLog
from odometer.models.vehicle import Vehicle
from odometer.services.exceptions import InvalidFuelLogError


def validate_fuel_history(
    vehicle: Vehicle, history: list[FuelLog], *, baseline: list[FuelLog] | None = None
) -> None:
    """Validate all candidate records before a caller persists any of them."""
    # Corrections may preserve an existing conflict, but cannot introduce or alter one.
    existing_edges = set()
    ordered_baseline = sorted(baseline or [], key=lambda item: (item.date, item.id))
    for left, right in zip(ordered_baseline, ordered_baseline[1:], strict=False):
        if right.odometer_miles < left.odometer_miles:
            existing_edges.add(
                (
                    left.id,
                    left.date,
                    left.odometer_miles,
                    right.id,
                    right.date,
                    right.odometer_miles,
                )
            )
    previous: FuelLog | None = None
    for row in sorted(history, key=lambda item: (item.date, item.id)):
        if row.vehicle_id != vehicle.id:
            raise InvalidFuelLogError("Fuel vehicle relationship cannot change.")
        if not isinstance(row.date, date):
            raise InvalidFuelLogError("Fuel date must be a date.")
        if not math.isfinite(row.litres) or row.litres <= 0:
            raise InvalidFuelLogError("Fuel litres must be greater than zero.")
        if type(row.total_cost_pence) is not int or row.total_cost_pence <= 0:
            raise InvalidFuelLogError("Fuel amount must be positive integer pence.")
        if type(row.odometer_miles) is not int or row.odometer_miles < vehicle.initial_mileage:
            raise InvalidFuelLogError("Fuel mileage cannot be lower than initial mileage.")
        if vehicle.fuel_tank_litres is None or row.litres > vehicle.fuel_tank_litres:
            raise InvalidFuelLogError("Fuel litres cannot exceed the vehicle fuel tank size.")
        if row.price_per_litre_pence is not None and (
            not math.isfinite(row.price_per_litre_pence) or row.price_per_litre_pence <= 0
        ):
            raise InvalidFuelLogError("Fuel price must be greater than zero.")
        if (
            previous is not None
            and row.odometer_miles < previous.odometer_miles
            and (
                previous.id,
                previous.date,
                previous.odometer_miles,
                row.id,
                row.date,
                row.odometer_miles,
            )
            not in existing_edges
        ):
            raise InvalidFuelLogError(
                f"Fuel mileage on {row.date} ({row.odometer_miles}) cannot be lower "
                f"than {previous.date} ({previous.odometer_miles})."
            )
        previous = row
