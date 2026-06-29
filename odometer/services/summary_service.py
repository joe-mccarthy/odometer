"""Summary service."""

from dataclasses import dataclass
from datetime import date

from sqlmodel import Session

from odometer.models.vehicle import Vehicle
from odometer.services.calculation_service import (
    CalculationService,
    CategoryBreakdownItem,
    PeriodSummary,
    RollingAverages,
)
from odometer.services.vehicle_service import VehicleService


@dataclass(frozen=True)
class OverallSummary:
    """Overall spend summary."""

    total_spend_pence: int
    fuel_spend_pence: int
    non_fuel_spend_pence: int
    expense_count: int
    fuel_log_count: int
    miles_driven: int | None
    running_cost_per_mile_pence: float | None
    ownership_cost_per_mile_pence: float | None
    average_monthly_spend_pence: int


class SummaryService:
    """Business logic for spend summaries."""

    def __init__(self, session: Session) -> None:
        """Create calculation and lookup dependencies for summary operations."""
        self.calculations = CalculationService(session)
        self.vehicle_service = VehicleService(session)
        self.expense_repository = self.calculations.expense_repository
        self.fuel_repository = self.calculations.fuel_repository

    def overall_summary(
        self,
        *,
        vehicle_identifier: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> OverallSummary:
        """Return an overall summary for one vehicle or a vehicle collection."""
        vehicles = self._resolve_vehicles(vehicle_identifier, include_inactive=include_inactive)
        total_spend = 0
        fuel_spend = 0
        non_fuel_spend = 0
        expense_count = 0
        fuel_log_count = 0
        total_miles = 0
        has_miles = False
        purchase_total = 0
        has_purchase_price = False

        for vehicle in vehicles:
            expenses = self.expense_repository.list(
                vehicle_id=vehicle.id,
                date_from=date_from,
                date_to=date_to,
                limit=None,
            )
            fuel_logs = self.fuel_repository.list(
                vehicle_id=vehicle.id,
                date_from=date_from,
                date_to=date_to,
                limit=None,
            )
            spend = self.calculations.spend_components(expenses, fuel_logs)
            total_spend += spend.total_spend_pence
            fuel_spend += spend.fuel_spend_pence
            non_fuel_spend += spend.expense_spend_pence
            expense_count += len(expenses)
            fuel_log_count += len(fuel_logs)

            miles = self._miles_for_summary(vehicle, date_from, date_to)
            if miles is not None:
                has_miles = True
                total_miles += miles

            if vehicle.purchase_price_pence is not None:
                has_purchase_price = True
                purchase_total += vehicle.purchase_price_pence

        rolling = self.calculations.rolling_averages(
            vehicle_identifier=vehicle_identifier,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )
        ownership_cost = total_spend + purchase_total if has_purchase_price else None
        miles_driven = total_miles if has_miles else None
        return OverallSummary(
            total_spend_pence=total_spend,
            fuel_spend_pence=fuel_spend,
            non_fuel_spend_pence=non_fuel_spend,
            expense_count=expense_count,
            fuel_log_count=fuel_log_count,
            miles_driven=miles_driven,
            running_cost_per_mile_pence=self.calculations.cost_per_mile_pence(
                total_spend, total_miles
            ),
            ownership_cost_per_mile_pence=self.calculations.cost_per_mile_pence(
                ownership_cost, total_miles
            ),
            average_monthly_spend_pence=rolling.all_months_average_pence,
        )

    def monthly_summary(
        self,
        *,
        vehicle_identifier: str | None = None,
        year: int | None = None,
        include_inactive: bool = False,
    ) -> list[PeriodSummary]:
        """Return monthly spend summaries."""
        return self.calculations.monthly_summaries(
            vehicle_identifier=vehicle_identifier,
            year=year,
            include_inactive=include_inactive,
        )

    def annual_summary(
        self, *, vehicle_identifier: str | None = None, include_inactive: bool = False
    ) -> list[PeriodSummary]:
        """Return annual spend summaries."""
        return self.calculations.annual_summaries(
            vehicle_identifier=vehicle_identifier,
            include_inactive=include_inactive,
        )

    def category_breakdown(
        self,
        *,
        vehicle_identifier: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> list[CategoryBreakdownItem]:
        """Return category breakdown."""
        return self.calculations.category_breakdown_for_scope(
            vehicle_identifier=vehicle_identifier,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )

    def rolling_averages(
        self,
        *,
        vehicle_identifier: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_inactive: bool = False,
    ) -> RollingAverages:
        """Return rolling averages."""
        return self.calculations.rolling_averages(
            vehicle_identifier=vehicle_identifier,
            date_from=date_from,
            date_to=date_to,
            include_inactive=include_inactive,
        )

    def _resolve_vehicles(
        self, vehicle_identifier: str | None, *, include_inactive: bool = False
    ) -> list[Vehicle]:
        """Return the single requested vehicle or the current summary fleet."""
        if vehicle_identifier is not None:
            return [self.vehicle_service.get_vehicle(vehicle_identifier)]
        return self.vehicle_service.list_vehicles(include_inactive=include_inactive)

    def _miles_for_summary(
        self, vehicle: Vehicle, date_from: date | None, date_to: date | None
    ) -> int | None:
        """Return lifetime or date-bounded mileage for an overall summary."""
        if date_from is None and date_to is None:
            expenses = self.expense_repository.list(vehicle_id=vehicle.id, limit=None)
            fuel_logs = self.fuel_repository.list(vehicle_id=vehicle.id, limit=None)
            return self.calculations.miles_driven(vehicle, expenses, fuel_logs)

        start = date_from or date.min
        end = date_to or date.max
        return self.calculations._period_miles_for_vehicle(vehicle, start, end)
