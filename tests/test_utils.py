"""Utility and small widget tests."""

from datetime import date

from odometer.tui.widgets.money import MoneyDisplay
from odometer.utils.dates import parse_date, parse_optional_date
from odometer.utils.formatting import format_date, format_optional_float
from odometer.utils.money import format_money, pence_to_pounds_decimal
from odometer.utils.registration import display_registration


def test_date_parsing_helpers() -> None:
    """Verify date helper handling for strings, dates, and empty optional values."""
    expected = date(2026, 6, 29)

    assert parse_date("2026-06-29") == expected
    assert parse_date(expected) == expected
    assert parse_optional_date("2026-06-29") == expected
    assert parse_optional_date(expected) == expected
    assert parse_optional_date(None) is None


def test_formatting_helpers_cover_empty_values() -> None:
    """Verify display helpers format missing and provided values consistently."""
    assert format_date(None) == "-"
    assert format_optional_float(None) == "-"
    assert format_optional_float(12.345, suffix=" mpg", precision=1) == "12.3 mpg"
    assert display_registration(" ab12 cde ") == "AB12 CDE"


def test_money_helpers_and_widget() -> None:
    """Verify money formatting helpers and the Textual money display widget."""
    assert format_money(None) == "-"
    assert format_money(-12345) == "-£123.45"
    assert pence_to_pounds_decimal(12345).as_tuple().exponent == -2

    widget = MoneyDisplay("Total", 12345)

    assert widget.content == "Total: £123.45"
