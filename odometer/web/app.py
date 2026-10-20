"""Service-backed HTTP routes for the local browser application."""

import logging
from collections.abc import Callable, Iterator
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, TypedDict

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlmodel import Session
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from odometer.db.bootstrap import initialise_database
from odometer.db.session import get_session
from odometer.models.enums import ExpenseCategory
from odometer.services import exceptions as exc
from odometer.services.calculation_service import CalculationService
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.summary_service import SummaryService
from odometer.services.vehicle_service import VehicleService
from odometer.web.schemas import ExpenseCreate, FuelCreate, FuelUpdate, VehicleCreate, VehiclePatch
from odometer.web.security import LocalBoundary, error

logger = logging.getLogger(__name__)
STATIC = Path(__file__).with_name("static")


class ListFilters(TypedDict, total=False):
    limit: int
    ascending: bool
    date_from: date
    date_to: date


class SummaryScope(TypedDict):
    vehicle_identifier: str | None
    include_inactive: bool


def wire(value: Any) -> Any:
    """SQLite stores naive UTC timestamps; make that timezone explicit on the wire."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(item) for item in value]
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")
    return jsonable_encoder(value)


def resource(value: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(wire(value), status_code=status_code)


class InputError(Exception):
    def __init__(self, message: str, fields: dict[str, str] | None = None) -> None:
        self.message = message
        self.fields = fields or {}


def call[T](method: Callable[..., T], **kwargs: Any) -> T:
    """Only classify ValueErrors from known service mutation validation."""
    try:
        return method(**kwargs)
    except ValueError as exception:
        raise InputError(str(exception)) from exception


def boolean(value: str, name: str) -> bool:
    if value not in {"true", "false"}:
        raise InputError("Invalid query boolean", {name: "Use true or false"})
    return value == "true"


def integer(value: str, name: str, low: int, high: int) -> int:
    if (
        len(value) > 16
        or not value.isascii()
        or not value.isdecimal()
        or not low <= int(value) <= high
    ):
        raise InputError("Invalid query integer", {name: f"Use an integer {low}..{high}"})
    return int(value)


def filters(request: Request) -> ListFilters:
    query = request.query_params
    result: ListFilters = {
        "limit": integer(query.get("limit", "50"), "limit", 1, 1000),
        "ascending": boolean(query.get("ascending", "false"), "ascending"),
    }
    for name in ("date_from", "date_to"):
        value = query.get(name)
        if value is not None:
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError
                result[name] = parsed
            except ValueError as exception:
                raise InputError("Invalid date", {name: "Use YYYY-MM-DD"}) from exception
    if result.get("date_from", date.min) > result.get("date_to", date.max):
        raise InputError("date_from must not follow date_to")
    return result


def create_app(database_path: Path | None = None, port: int = 8765) -> FastAPI:
    """Build an app with request-local sessions and an explicit local authority."""
    if not 1 <= port <= 65535:
        raise ValueError("Port must be 1..65535")
    path = initialise_database(database_path)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LocalBoundary, port=port)

    def session() -> Iterator[Session]:
        with get_session(path) as current:
            try:
                yield current
            except Exception:
                current.rollback()
                raise

    @app.exception_handler(InputError)
    async def input_error(request: Request, exception: InputError) -> JSONResponse:
        return error(422, "validation_error", exception.message, exception.fields)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exception: RequestValidationError) -> JSONResponse:
        errors = exception.errors()
        malformed = any(item["type"] == "json_invalid" for item in errors)
        return error(
            400 if malformed else 422,
            "invalid_json" if malformed else "validation_error",
            "Malformed JSON" if malformed else "Invalid request",
            {".".join(map(str, item["loc"])): item["msg"] for item in errors},
        )

    @app.exception_handler(exc.OdometerError)
    async def service_error(request: Request, exception: exc.OdometerError) -> JSONResponse:
        if isinstance(
            exception,
            (exc.VehicleNotFoundError, exc.ExpenseNotFoundError, exc.FuelLogNotFoundError),
        ):
            return error(404, "not_found", str(exception))
        if isinstance(exception, exc.DuplicateActiveVehicleError):
            return error(409, "duplicate_vehicle", str(exception))
        if isinstance(exception, (exc.InvalidExpenseError, exc.InvalidFuelLogError)):
            return error(422, "validation_error", str(exception))
        return error(500, "internal_error", "An internal error occurred")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exception: HTTPException) -> JSONResponse:
        return error(
            exception.status_code,
            "method_not_allowed" if exception.status_code == 405 else "not_found",
            "Method not allowed" if exception.status_code == 405 else "Not found",
        )

    @app.exception_handler(OperationalError)
    async def database_error(request: Request, exception: OperationalError) -> JSONResponse:
        if any(word in str(exception.orig).lower() for word in ("locked", "busy")):
            return error(503, "database_busy", "Database is busy; try again shortly")
        logger.error("Database operation failed", exc_info=exception)
        return error(500, "internal_error", "An internal error occurred")

    session_dependency = Depends(session)

    @app.get("/api/vehicles")
    def vehicles(include_inactive: str = "false", db: Session = session_dependency) -> JSONResponse:
        return resource(
            VehicleService(db).list_vehicles(boolean(include_inactive, "include_inactive"))
        )

    @app.post("/api/vehicles", status_code=201)
    def create_vehicle(body: VehicleCreate, db: Session = session_dependency) -> JSONResponse:
        return resource(
            call(VehicleService(db).create_vehicle, **body.model_dump()), status_code=201
        )

    @app.get("/api/vehicles/{vehicle_id}")
    def vehicle(vehicle_id: str, db: Session = session_dependency) -> JSONResponse:
        return resource(VehicleService(db).get_vehicle(vehicle_id))

    @app.patch("/api/vehicles/{vehicle_id}")
    def patch_vehicle(
        vehicle_id: str, body: VehiclePatch, db: Session = session_dependency
    ) -> JSONResponse:
        service = VehicleService(db)
        if body.status:
            method = service.mark_vehicle_sold if body.status == "SOLD" else service.archive_vehicle
            return resource(method(vehicle_id))
        return resource(
            call(
                service.set_fuel_tank_capacity,
                identifier=vehicle_id,
                fuel_tank_litres=body.fuel_tank_litres,
            )
        )

    @app.delete("/api/vehicles/{vehicle_id}")
    def delete_vehicle(vehicle_id: str, db: Session = session_dependency) -> JSONResponse:
        return resource(VehicleService(db).delete_vehicle(vehicle_id))

    @app.get("/api/vehicles/{vehicle_id}/fuel")
    def fuel(vehicle_id: str, request: Request, db: Session = session_dependency) -> JSONResponse:
        return resource(
            FuelService(db).list_fuel_logs(vehicle_identifier=vehicle_id, **filters(request))
        )

    @app.post("/api/vehicles/{vehicle_id}/fuel", status_code=201)
    def create_fuel(
        vehicle_id: str, body: FuelCreate, db: Session = session_dependency
    ) -> JSONResponse:
        values = body.model_dump()
        values["date_"] = values.pop("date")
        return resource(
            call(FuelService(db).add_fuel_log, vehicle_identifier=vehicle_id, **values),
            status_code=201,
        )

    @app.put("/api/fuel/{fuel_id}")
    def update_fuel(
        fuel_id: str, body: FuelUpdate, db: Session = session_dependency
    ) -> JSONResponse:
        values = body.model_dump(exclude={"fuel_tank_litres"})
        values["date_"] = values.pop("date")
        return resource(call(FuelService(db).update_fuel_log, fuel_log_id=fuel_id, **values))

    @app.delete("/api/fuel/{fuel_id}")
    def delete_fuel(fuel_id: str, db: Session = session_dependency) -> JSONResponse:
        return resource(FuelService(db).delete_fuel_log(fuel_id))

    @app.get("/api/vehicles/{vehicle_id}/expenses")
    def expenses(
        vehicle_id: str,
        request: Request,
        category: ExpenseCategory | None = None,
        db: Session = session_dependency,
    ) -> JSONResponse:
        return resource(
            ExpenseService(db).list_expenses(
                vehicle_identifier=vehicle_id, category=category, **filters(request)
            )
        )

    @app.post("/api/vehicles/{vehicle_id}/expenses", status_code=201)
    def create_expense(
        vehicle_id: str, body: ExpenseCreate, db: Session = session_dependency
    ) -> JSONResponse:
        values = body.model_dump()
        values["date_"] = values.pop("date")
        return resource(
            call(ExpenseService(db).add_expense, vehicle_identifier=vehicle_id, **values),
            status_code=201,
        )

    @app.put("/api/expenses/{expense_id}")
    def update_expense(
        expense_id: str, body: ExpenseCreate, db: Session = session_dependency
    ) -> JSONResponse:
        values = body.model_dump()
        values["date_"] = values.pop("date")
        return resource(call(ExpenseService(db).update_expense, expense_id=expense_id, **values))

    @app.delete("/api/expenses/{expense_id}")
    def delete_expense(expense_id: str, db: Session = session_dependency) -> JSONResponse:
        return resource(ExpenseService(db).delete_expense(expense_id))

    @app.get("/api/summary")
    def summary(
        vehicle_id: str | None = None,
        include_inactive: str = "false",
        year: str | None = None,
        db: Session = session_dependency,
    ) -> JSONResponse:
        scope: SummaryScope = {
            "vehicle_identifier": vehicle_id,
            "include_inactive": boolean(include_inactive, "include_inactive"),
        }
        selected_year = integer(year, "year", 1, 9998) if year is not None else None
        service = SummaryService(db)
        mpg = None
        if vehicle_id:
            try:
                mpg = CalculationService(db).mpg_stats(vehicle_id)
            except exc.CalculationUnavailableError:
                pass
        return resource(
            jsonable_encoder(
                {
                    "overall": service.overall_summary(**scope),
                    "monthly": service.monthly_summary(year=selected_year, **scope),
                    "annual": service.annual_summary(**scope),
                    "categories": service.category_breakdown(**scope),
                    "rolling": service.rolling_averages(**scope),
                    "mpg": mpg,
                }
            )
        )

    @app.get("/")
    def index() -> FileResponse:
        if not (STATIC / "index.html").is_file():
            raise HTTPException(404)
        return FileResponse(STATIC / "index.html")

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
