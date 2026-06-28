"""General display formatting helpers."""

from datetime import date


def format_date(value: date | None) -> str:
    """Format a date for display."""
    return value.isoformat() if value else "-"


def format_optional_int(value: int | None) -> str:
    """Format an optional integer."""
    return f"{value:,}" if value is not None else "-"


def format_optional_float(value: float | None, suffix: str = "", precision: int = 2) -> str:
    """Format an optional float."""
    if value is None:
        return "-"
    return f"{value:.{precision}f}{suffix}"
