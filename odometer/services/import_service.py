"""Validated append-only version-one imports; no writes during preview."""

import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import create_model

from odometer.models import Expense
from odometer.models.enums import VehicleStatus
from odometer.services.exceptions import InvalidExpenseError, InvalidFuelLogError
from odometer.services.history_validation import validate_expense, validate_fuel_history
from odometer.services.portability_service import TABLES, backup_database
from odometer.utils.registration import normalise_registration


@dataclass
class ImportPreview:
    """Intended counts and located diagnostics, including invalid rows."""

    counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    rows: dict[str, list] = field(default_factory=dict)


def preview_import(source: Path, target: Path, conflict_policy: str) -> ImportPreview:
    """Parse and validate without creating the target or its parent."""
    result = ImportPreview()
    if conflict_policy != "reject":
        result.errors.append("conflict_policy: only reject is supported")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        result.errors.append(f"JSON: {exc}")
        return result
    if not isinstance(data, dict):
        result.errors.append("schema: expected an object")
        return result
    if type(data.get("format_version")) is not int or data["format_version"] != 1:
        result.errors.append("format_version: only version 1 is supported")
    if data.keys() - {"format_version", *TABLES}:
        result.errors.append("schema: unknown top-level fields")
    for name, model in TABLES.items():
        values = data.get(name)
        result.rows[name] = []
        if not isinstance(values, list):
            result.errors.append(f"{name}: expected an array")
            continue
        result.counts[name] = len(values)
        ids = set()
        for index, value in enumerate(values):
            location = f"{name}[{index}]"
            try:
                if not isinstance(value, dict):
                    raise ValueError("expected an object")
                if value.keys() - model.model_fields.keys():
                    raise ValueError("unknown fields")
                if not isinstance(value.get("id"), str) or not value["id"].strip():
                    raise ValueError("nonempty id is required")
                if value["id"] in ids:
                    result.errors.append(f"{location}.id: duplicate ID {value['id']}")
                ids.add(value["id"])
                # Strict JSON validation accepts ISO dates/enums but rejects coercive money/bools.
                fields: dict[str, Any] = {
                    key: (info.annotation, info) for key, info in model.model_fields.items()
                }
                schema = create_model(f"{name}Import", **fields)
                parsed = schema.model_validate_json(json.dumps(value), strict=True)
                row = model.model_validate(parsed.model_dump())
                for key in model.model_fields:
                    item = getattr(row, key)
                    # bool is a separate JSON type, although it subclasses int in Python.
                    if type(item) is int and not -(2**63) <= item <= 2**63 - 1:
                        result.errors.append(
                            f"{location}.{key}: must fit SQLite signed 64-bit integer range"
                        )
                    if isinstance(item, float) and not math.isfinite(item):
                        raise ValueError(f"{key}: must be finite")
                result.rows[name].append(row)
            except ValueError as exc:
                result.errors.append(f"{location}: {exc}")
    vehicles = {row.id: row for row in result.rows["vehicles"]}
    registrations = set()
    for vehicle in vehicles.values():
        try:
            normalised = normalise_registration(vehicle.registration)
            if not normalised or normalised != vehicle.normalised_registration:
                raise ValueError("registration normalization mismatch")
            if vehicle.initial_mileage < 0:
                raise ValueError("initial mileage must be nonnegative")
            if vehicle.fuel_tank_litres is not None and vehicle.fuel_tank_litres <= 0:
                raise ValueError("tank capacity must be positive")
            if vehicle.purchase_price_pence is not None and vehicle.purchase_price_pence < 0:
                raise ValueError("purchase price must be nonnegative integer pence")
            if vehicle.status == VehicleStatus.ACTIVE:
                if normalised in registrations:
                    raise ValueError("duplicate active registration")
                registrations.add(normalised)
        except ValueError as exc:
            result.errors.append(f"vehicles[{vehicle.id}]: {exc}")
    for name in ("fuel", "expenses"):
        for row in result.rows[name]:
            vehicle = vehicles.get(row.vehicle_id)
            if vehicle is None:
                result.errors.append(f"{name}[{row.id}].vehicle_id: missing imported vehicle")
            elif isinstance(row, Expense):
                try:
                    validate_expense(vehicle, row)
                except InvalidExpenseError as exc:
                    result.errors.append(f"expenses[{row.id}]: {exc}")
    for vehicle in vehicles.values():
        try:
            validate_fuel_history(
                vehicle, [r for r in result.rows["fuel"] if r.vehicle_id == vehicle.id]
            )
        except (ValueError, InvalidFuelLogError) as exc:
            result.errors.append(f"fuel[{vehicle.id}]: {exc}")
    if target.exists():
        try:
            with sqlite3.connect(target.resolve().as_uri() + "?mode=ro", uri=True) as db:
                _conflicts(db, result)
        except sqlite3.Error as exc:
            result.errors.append(f"target: {exc}")
    return result


def _conflicts(db: sqlite3.Connection, result: ImportPreview) -> None:
    for name, table in (("vehicles", "vehicle"), ("fuel", "fuellog"), ("expenses", "expense")):
        for row in result.rows.get(name, []):
            if db.execute(f"SELECT 1 FROM {table} WHERE id=?", (row.id,)).fetchone():
                result.errors.append(f"{name}[{row.id}]: target ID collision")
    for row in result.rows.get("vehicles", []):
        if (
            row.status == VehicleStatus.ACTIVE
            and db.execute(
                "SELECT 1 FROM vehicle WHERE normalised_registration=? AND status=?",
                (row.normalised_registration, VehicleStatus.ACTIVE.name),
            ).fetchone()
        ):
            result.errors.append(f"vehicles[{row.id}]: target active registration collision")


def import_data(
    source: Path,
    target: Path,
    *,
    conflict_policy: str,
    dry_run: bool = False,
    backup: Path | None = None,
) -> ImportPreview:
    """Validate first, then recheck conflicts under a SQLite writer lock and commit once."""
    result = preview_import(source, target, conflict_policy)
    if dry_run or result.errors:
        return result
    if backup is not None:
        backup_database(target, backup)
    # A missing destination is initialized only after the entire input is valid.
    from odometer.db.bootstrap import initialise_database

    if not target.exists():
        initialise_database(target)
    with sqlite3.connect(target) as db:
        db.execute("BEGIN IMMEDIATE")
        _conflicts(db, result)
        if result.errors:
            db.rollback()
            return result
        for name, table in (("vehicles", "vehicle"), ("fuel", "fuellog"), ("expenses", "expense")):
            for row in result.rows[name]:
                values = row.model_dump(mode="json")
                for key in ("status", "category"):
                    if key in values:
                        values[key] = getattr(row, key).name
                columns = ",".join(f'"{key}"' for key in values)
                placeholders = ",".join("?" for _ in values)
                db.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                    tuple(values.values()),
                )
    return result
