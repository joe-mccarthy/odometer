"""Database bootstrap helpers."""

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

# Import models so SQLModel metadata is populated before create_all is called.
import odometer.models  # noqa: F401
from odometer.db.session import get_database_path, get_engine


def _ensure_vehicle_schema(engine: Engine) -> None:
    """Apply lightweight SQLite schema updates for existing databases."""
    with engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(vehicle)").all()}
        if columns and "fuel_tank_litres" not in columns:
            connection.exec_driver_sql("ALTER TABLE vehicle ADD COLUMN fuel_tank_litres FLOAT")


def initialise_database(database_path: Path | None = None) -> Path:
    """Create database tables if they do not already exist."""
    path = database_path or get_database_path()
    engine = get_engine(path)
    try:
        SQLModel.metadata.create_all(engine)
        _ensure_vehicle_schema(engine)
    finally:
        engine.dispose()
    return path
