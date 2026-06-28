"""Money parsing and formatting helpers."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PENCE_PER_POUND = 100


class MoneyParseError(ValueError):
    """Raised when a money value cannot be parsed."""


def parse_money_to_pence(value: str | Decimal | int) -> int:
    """Parse a pounds value into integer pence."""
    try:
        pounds = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise MoneyParseError(f"Invalid money value: {value}") from exc

    return int(pounds * PENCE_PER_POUND)


def format_money(pence: int | None) -> str:
    """Format integer pence as GBP."""
    if pence is None:
        return "-"
    sign = "-" if pence < 0 else ""
    absolute = abs(pence)
    pounds, pennies = divmod(absolute, PENCE_PER_POUND)
    return f"{sign}£{pounds:,}.{pennies:02d}"


def pence_to_pounds_decimal(pence: int) -> Decimal:
    """Convert pence to a Decimal pounds value."""
    return (Decimal(pence) / PENCE_PER_POUND).quantize(Decimal("0.01"))
