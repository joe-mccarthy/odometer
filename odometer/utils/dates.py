"""Date parsing helpers."""

from datetime import date


def parse_date(value: str | date | None) -> date:
    """Parse an ISO yyyy-mm-dd date, defaulting to today."""
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def parse_optional_date(value: str | date | None) -> date | None:
    """Parse an optional ISO yyyy-mm-dd date."""
    if value is None:
        return None
    return parse_date(value)
