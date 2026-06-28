"""Calculation engine for Odometer."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session

from odometer.models.enums import ExpenseCategory
from odometer.models.expense import Expense
from odometer.models.fuel import FuelLog
from odometer.models.vehicle import Vehicle
from odometer.repositories.expense_repository import ExpenseRepository
from odometer.repositories.fuel_repository import FuelRepository
from odometer.services.exceptions import CalculationUnavailableError
from odometer.services.vehicle_service import VehicleService

IMPERIAL_GALLON_LITRES = 4.54609


@dataclass(frozen=True)
class SpendComponents:
    """Spend split for a scope."""

    total_spend_pence: int
    fuel_spend_pence: int
    expense_spend_pence: int


@dataclass(frozen=True)
class VehicleCostMetrics:
    """Cost metrics for a vehicle."""

    vehicle: Vehicle
    latest_mileage: int
    miles_driven: int
    running_cost_pence: int
    ownership_cost_pence: int | None
    running_cost_per_mile_pence: float | None
    ownership_cost_per_mile_pence: float | None


@dataclass(frozen=True)
class MPGSegment:
    """A full-to-full fuel economy segment."""

    start_odometer_miles: int
    end_odometer_miles: int
    miles: int
    litres: float
    uk_mpg: float
    date: date


@dataclass(frozen=True)
class MPGStats:
    """Fuel economy statistics."""

    latest_mpg: float
    average_mpg: float
    best_mpg: float
    worst_mpg: float
    segment_count: int


@dataclass(frozen=True)
class CategoryBreakdownItem:
    """Spend by category."""

    category: ExpenseCategory
    amount_pence: int
    percentage: float
    count: int


@dataclass(frozen=True)
class PeriodSummary:
    """Spend summary for a month or year."""

    period: str
    total_spend_pence: int
    fuel_spend_pence: int
    expense_spend_pence: int
    miles_driven: int | None
    cost_per_mile_pence: float | None


@dataclass(frozen=True)
class RollingAverages:
    """Rolling monthly average spend."""

    all_months_average_pence: int
    last_3_months_average_pence: int
    last_6_months_average_pence: int
    last_12_months_average_pence: int


class CalculationService:
    """Reusable calculations over vehicle, expense, and fuel data."""

    def __init__(self, session: Session) -> None:
        self.expense_repository = ExpenseRepository(session)
        self.fuel_repository = FuelRepository(session)
        self.vehicle_service = VehicleService(session)

    @staticmethod
    def latest_known_mileage(
        vehicle: Vehicle, expenses: Iterable[Expense], fuel_logs: Iterable[FuelLog]
    ) -> int:
        """Return the latest known odometer reading."""
        readings = [vehicle.initial_mileage]
        readings.extend(
            expense.odometer_miles for expense in expenses if expense.odometer_miles is not None
        )
        readings.extend(fuel_log.odometer_miles for fuel_log in fuel_logs)
        return max(readings)

    @classmethod
    def miles_driven(
        cls, vehicle: Vehicle, expenses: Iterable[Expense], fuel_logs: Iterable[FuelLog]
    ) -> int:
        """Return miles driven since the vehicle's initial mileage."""
        latest_mileage = cls.latest_known_mileage(vehicle, expenses, fuel_logs)
        return max(latest_mileage - vehicle.initial_mileage, 0)

    @staticmethod
    def spend_components(
        expenses: Iterable[Expense], fuel_logs: Iterable[FuelLog]
    ) -> SpendComponents:
        """Return fuel and non-fuel spend, avoiding obvious fuel double counting."""
        expense_list = list(expenses)
        fuel_log_list = list(fuel_logs)
        fuel_log_total = sum(fuel_log.total_cost_pence for fuel_log in fuel_log_list)
        fuel_expense_total = sum(
            expense.amount_pence
            for expense in expense_list
            if expense.category == ExpenseCategory.FUEL
        )
        non_fuel_expense_total = sum(
            expense.amount_pence
            for expense in expense_list
            if expense.category != ExpenseCategory.FUEL
        )

        if fuel_log_list:
            fuel_spend = fuel_log_total
        else:
            fuel_spend = fuel_expense_total

        total = fuel_spend + non_fuel_expense_total
        return SpendComponents(
            total_spend_pence=total,
            fuel_spend_pence=fuel_spend,
            expense_spend_pence=non_fuel_expense_total,
        )

    @staticmethod
    def ownership_cost_pence(vehicle: Vehicle, running_cost_pence: int) -> int | None:
        """Return running cost plus purchase price when available."""
        if vehicle.purchase_price_pence is None:
            return None
        return running_cost_pence + vehicle.purchase_price_pence

    @staticmethod
    def cost_per_mile_pence(cost_pence: int | None, miles_driven: int) -> float | None:
        """Return pence per mile when mileage is available."""
        if cost_pence is None or miles_driven <= 0:
            return None
        return cost_pence / miles_driven

    @staticmethod
    def mpg_segments(fuel_logs: Iterable[FuelLog]) -> list[MPGSegment]:
        """Calculate UK MPG segments from full-to-full fuel logs.

        Partial fills are included in fuel spend elsewhere but excluded from MPG calculation
        in this first implementation.
        """
        sorted_logs = sorted(fuel_logs, key=lambda log: (log.odometer_miles, log.date))
        previous_full: FuelLog | None = None
        segments: list[MPGSegment] = []

        for fuel_log in sorted_logs:
            if not fuel_log.is_full_tank:
                continue
            if previous_full is None:
                previous_full = fuel_log
                continue

            miles = fuel_log.odometer_miles - previous_full.odometer_miles
            if miles > 0 and fuel_log.litres > 0:
                uk_mpg = miles / (fuel_log.litres / IMPERIAL_GALLON_LITRES)
                segments.append(
                    MPGSegment(
                        start_odometer_miles=previous_full.odometer_miles,
                        end_odometer_miles=fuel_log.odometer_miles,
                        miles=miles,
                        litres=fuel_log.litres,
                        uk_mpg=uk_mpg,
                        date=fuel_log.date,
                    )
                )
            previous_full = fuel_log

        return segments

    @classmethod
    def mpg_stats_from_logs(cls, fuel_logs: Iterable[FuelLog]) -> MPGStats:
        """Return UK MPG stats from fuel logs."""
        segments = cls.mpg_segments(fuel_logs)
        if not segments:
            raise CalculationUnavailableError("No full-to-full fuel segments are available yet.")

        mpg_values = [segment.uk_mpg for segment in segments]
        return MPGStats(
            latest_mpg=segments[-1].uk_mpg,
            average_mpg=sum(mpg_values) / len(mpg_values),
            best_mpg=max(mpg_values),
            worst_mpg=min(mpg_values),
            segment_count=len(segments),
        )

    @staticmethod
    def category_breakdown(
        expenses: Iterable[Expense], fuel_logs: Iterable[FuelLog]
    ) -> list[CategoryBreakdownItem]:
        """Return category totals and percentages."""
        expense_list = list(expenses)
        fuel_log_list = list(fuel_logs)
        totals: dict[ExpenseCategory, int] = defaultdict(int)
        counts: dict[ExpenseCategory, int] = defaultdict(int)

        if fuel_log_list:
            totals[ExpenseCategory.FUEL] += sum(log.total_cost_pence for log in fuel_log_list)
            counts[ExpenseCategory.FUEL] += len(fuel_log_list)
            expenses_to_count = [
                expense for expense in expense_list if expense.category != ExpenseCategory.FUEL
            ]
        else:
            expenses_to_count = expense_list

        for expense in expenses_to_count:
            totals[expense.category] += expense.amount_pence
            counts[expense.category] += 1

        total_spend = sum(totals.values())
        if total_spend == 0:
            return []

        return [
            CategoryBreakdownItem(
                category=category,
                amount_pence=amount,
                percentage=(amount / total_spend) * 100,
                count=counts[category],
            )
            for category, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True)
        ]

    def vehicle_cost_metrics(
        self, vehicle_identifier: str | None = None
    ) -> list[VehicleCostMetrics]:
        """Return cost metrics for one vehicle or all active vehicles."""
        vehicles = self._resolve_vehicles(vehicle_identifier)
        return [self._vehicle_cost_metrics(vehicle) for vehicle in vehicles]

    def mpg_stats(self, vehicle_identifier: str) -> MPGStats:
        """Return MPG stats for a vehicle."""
        vehicle = self.vehicle_service.get_vehicle(vehicle_identifier)
        fuel_logs = self.fuel_repository.list(vehicle_id=vehicle.id, limit=None, ascending=True)
        return self.mpg_stats_from_logs(fuel_logs)

    def category_breakdown_for_scope(
        self,
        *,
        vehicle_identifier: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[CategoryBreakdownItem]:
        """Return category breakdown for a vehicle or active fleet."""
        vehicles = self._resolve_vehicles(vehicle_identifier)
        breakdowns: dict[ExpenseCategory, tuple[int, int]] = defaultdict(lambda: (0, 0))

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
            for item in self.category_breakdown(expenses, fuel_logs):
                amount, count = breakdowns[item.category]
                breakdowns[item.category] = (amount + item.amount_pence, count + item.count)

        total = sum(amount for amount, _count in breakdowns.values())
        if total == 0:
            return []
        return [
            CategoryBreakdownItem(
                category=category,
                amount_pence=amount,
                percentage=(amount / total) * 100,
                count=count,
            )
            for category, (amount, count) in sorted(
                breakdowns.items(), key=lambda item: item[1][0], reverse=True
            )
        ]

    def monthly_summaries(
        self, *, vehicle_identifier: str | None = None, year: int | None = None
    ) -> list[PeriodSummary]:
        """Return monthly spend summaries."""
        selected_year = year or date.today().year
        vehicles = self._resolve_vehicles(vehicle_identifier)
        summaries: list[PeriodSummary] = []
        for month in range(1, 13):
            start = date(selected_year, month, 1)
            end = _month_end(start)
            summaries.append(self._period_summary(vehicles, start, end, start.strftime("%Y-%m")))
        return summaries

    def annual_summaries(self, *, vehicle_identifier: str | None = None) -> list[PeriodSummary]:
        """Return annual spend summaries for years with data."""
        vehicles = self._resolve_vehicles(vehicle_identifier)
        years = self._years_with_data(vehicles)
        summaries: list[PeriodSummary] = []
        for year in years:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            summaries.append(self._period_summary(vehicles, start, end, str(year)))
        return summaries

    def rolling_averages(
        self,
        *,
        vehicle_identifier: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> RollingAverages:
        """Return rolling monthly average spend."""
        vehicles = self._resolve_vehicles(vehicle_identifier)
        transactions = self._transaction_dates(vehicles, date_from=date_from, date_to=date_to)
        if not transactions:
            return RollingAverages(0, 0, 0, 0)

        first_month = _month_start(min(transactions))
        last_month = _month_start(max(transactions))
        month_totals: dict[str, int] = {}
        current = first_month
        while current <= last_month:
            summary = self._period_summary(
                vehicles, current, _month_end(current), current.strftime("%Y-%m")
            )
            month_totals[current.strftime("%Y-%m")] = summary.total_spend_pence
            current = _add_months(current, 1)

        ordered_totals = list(month_totals.values())
        return RollingAverages(
            all_months_average_pence=round(sum(ordered_totals) / len(ordered_totals)),
            last_3_months_average_pence=_trailing_average(ordered_totals, 3),
            last_6_months_average_pence=_trailing_average(ordered_totals, 6),
            last_12_months_average_pence=_trailing_average(ordered_totals, 12),
        )

    def _vehicle_cost_metrics(self, vehicle: Vehicle) -> VehicleCostMetrics:
        expenses = self.expense_repository.list(vehicle_id=vehicle.id, limit=None)
        fuel_logs = self.fuel_repository.list(vehicle_id=vehicle.id, limit=None)
        latest_mileage = self.latest_known_mileage(vehicle, expenses, fuel_logs)
        miles = max(latest_mileage - vehicle.initial_mileage, 0)
        spend = self.spend_components(expenses, fuel_logs)
        ownership_cost = self.ownership_cost_pence(vehicle, spend.total_spend_pence)
        return VehicleCostMetrics(
            vehicle=vehicle,
            latest_mileage=latest_mileage,
            miles_driven=miles,
            running_cost_pence=spend.total_spend_pence,
            ownership_cost_pence=ownership_cost,
            running_cost_per_mile_pence=self.cost_per_mile_pence(spend.total_spend_pence, miles),
            ownership_cost_per_mile_pence=self.cost_per_mile_pence(ownership_cost, miles),
        )

    def _resolve_vehicles(self, vehicle_identifier: str | None) -> list[Vehicle]:
        if vehicle_identifier is not None:
            return [self.vehicle_service.get_vehicle(vehicle_identifier)]
        return self.vehicle_service.list_vehicles(include_inactive=False)

    def _period_summary(
        self, vehicles: list[Vehicle], start: date, end: date, period: str
    ) -> PeriodSummary:
        total_spend = 0
        fuel_spend = 0
        expense_spend = 0
        total_miles = 0
        has_mileage = False

        for vehicle in vehicles:
            expenses = self.expense_repository.list(
                vehicle_id=vehicle.id,
                date_from=start,
                date_to=end,
                limit=None,
            )
            fuel_logs = self.fuel_repository.list(
                vehicle_id=vehicle.id,
                date_from=start,
                date_to=end,
                limit=None,
            )
            spend = self.spend_components(expenses, fuel_logs)
            total_spend += spend.total_spend_pence
            fuel_spend += spend.fuel_spend_pence
            expense_spend += spend.expense_spend_pence

            miles = self._period_miles_for_vehicle(vehicle, start, end)
            if miles is not None:
                has_mileage = True
                total_miles += miles

        miles_driven = total_miles if has_mileage else None
        return PeriodSummary(
            period=period,
            total_spend_pence=total_spend,
            fuel_spend_pence=fuel_spend,
            expense_spend_pence=expense_spend,
            miles_driven=miles_driven,
            cost_per_mile_pence=self.cost_per_mile_pence(total_spend, total_miles),
        )

    def _period_miles_for_vehicle(self, vehicle: Vehicle, start: date, end: date) -> int | None:
        all_expenses = self.expense_repository.list(
            vehicle_id=vehicle.id, limit=None, ascending=True
        )
        all_fuel_logs = self.fuel_repository.list(vehicle_id=vehicle.id, limit=None, ascending=True)

        previous_readings = [vehicle.initial_mileage]
        period_readings: list[int] = []

        for expense in all_expenses:
            if expense.odometer_miles is None:
                continue
            if expense.date < start:
                previous_readings.append(expense.odometer_miles)
            elif start <= expense.date <= end:
                period_readings.append(expense.odometer_miles)

        for fuel_log in all_fuel_logs:
            if fuel_log.date < start:
                previous_readings.append(fuel_log.odometer_miles)
            elif start <= fuel_log.date <= end:
                period_readings.append(fuel_log.odometer_miles)

        if not period_readings:
            return None

        baseline = max(previous_readings)
        latest = max(period_readings)
        return max(latest - baseline, 0)

    def _years_with_data(self, vehicles: list[Vehicle]) -> list[int]:
        years = sorted(
            {transaction_date.year for transaction_date in self._transaction_dates(vehicles)}
        )
        return years or [date.today().year]

    def _transaction_dates(
        self,
        vehicles: list[Vehicle],
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[date]:
        dates: list[date] = []
        for vehicle in vehicles:
            dates.extend(
                expense.date
                for expense in self.expense_repository.list(
                    vehicle_id=vehicle.id,
                    date_from=date_from,
                    date_to=date_to,
                    limit=None,
                )
            )
            dates.extend(
                fuel_log.date
                for fuel_log in self.fuel_repository.list(
                    vehicle_id=vehicle.id,
                    date_from=date_from,
                    date_to=date_to,
                    limit=None,
                )
            )
        return dates


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_end(value: date) -> date:
    return _add_months(_month_start(value), 1) - timedelta(days=1)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _trailing_average(values: list[int], window: int) -> int:
    if not values:
        return 0
    selected = values[-window:]
    return round(sum(selected) / len(selected))
