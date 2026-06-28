"""Enumerations used by the domain models."""

from enum import StrEnum


class VehicleStatus(StrEnum):
    """Vehicle lifecycle state."""

    ACTIVE = "ACTIVE"
    SOLD = "SOLD"
    ARCHIVED = "ARCHIVED"


class ExpenseCategory(StrEnum):
    """Supported expense categories."""

    FUEL = "FUEL"
    SERVICE = "SERVICE"
    MOT = "MOT"
    INSURANCE = "INSURANCE"
    TAX = "TAX"
    REPAIR = "REPAIR"
    FINANCE = "FINANCE"
    TYRES = "TYRES"
    CLEANING = "CLEANING"
    PARKING = "PARKING"
    TOLL = "TOLL"
    FINE = "FINE"
    ACCESSORY = "ACCESSORY"
    OTHER = "OTHER"

    @classmethod
    def from_input(cls, value: str) -> "ExpenseCategory":
        """Parse CLI/user input into an expense category."""
        normalised = value.strip().upper().replace("-", "_").replace(" ", "_")
        return cls(normalised)
