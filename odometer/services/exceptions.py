"""Expected service-layer exceptions."""


class OdometerError(Exception):
    """Base class for expected application errors."""


class VehicleNotFoundError(OdometerError):
    """Raised when a vehicle cannot be found."""


class ExpenseNotFoundError(OdometerError):
    """Raised when an expense cannot be found."""


class FuelLogNotFoundError(OdometerError):
    """Raised when a fuel log cannot be found."""


class DuplicateActiveVehicleError(OdometerError):
    """Raised when creating a duplicate active registration."""


class InvalidExpenseError(OdometerError):
    """Raised when an expense fails validation."""


class InvalidFuelLogError(OdometerError):
    """Raised when a fuel log fails validation."""


class CalculationUnavailableError(OdometerError):
    """Raised when a calculation cannot be made from available data."""
