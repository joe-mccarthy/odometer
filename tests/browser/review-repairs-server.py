"""Serve fresh disposable imported records for review-repairs.cjs on loopback."""

import os
from datetime import date
from pathlib import Path

import uvicorn

from odometer.db.bootstrap import initialise_database
from odometer.db.session import get_session
from odometer.models.enums import ExpenseCategory
from odometer.models.expense import Expense
from odometer.models.fuel import FuelLog
from odometer.services.vehicle_service import VehicleService
from odometer.web.app import create_app


def main() -> None:
    """Refuse existing databases, seed cross-table ID overlaps, then serve locally."""
    path = Path(os.environ["ODOMETER_DB_PATH"])
    if path.exists():
        raise SystemExit("Use a new disposable ODOMETER_DB_PATH for this regression.")
    initialise_database()
    with get_session() as db:
        vehicle = VehicleService(db).create_vehicle(
            registration="EXACT48", initial_mileage=0, fuel_tank_litres=60
        )
        for i, amount in enumerate([9007199254740990, 9007199254740993, 9223372036854775807]):
            db.add(
                FuelLog(
                    id=f"shared{i}",
                    vehicle_id=vehicle.id,
                    date=date(2026, 1, i + 1),
                    odometer_miles=i,
                    litres=20,
                    total_cost_pence=amount,
                    price_per_litre_pence=None,
                )
            )
            db.add(
                Expense(
                    id=f"shared{i}",
                    vehicle_id=vehicle.id,
                    date=date(2026, 1, i + 1),
                    category=ExpenseCategory.SERVICE,
                    amount_pence=amount,
                )
            )
        for i in range(55):
            db.add(
                Expense(
                    id=f"older{i:02}",
                    vehicle_id=vehicle.id,
                    date=date(2025, 1, 1),
                    category=ExpenseCategory.SERVICE,
                    amount_pence=100,
                )
            )
        db.commit()
    port = int(os.environ.get("PORT", "8899"))
    uvicorn.run(create_app(port=port), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
