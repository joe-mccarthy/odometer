"""Money display widget."""

from textual.widgets import Static

from odometer.utils.money import format_money


class MoneyDisplay(Static):
    """Display a pence value as GBP."""

    def __init__(
        self,
        label: str,
        amount_pence: int | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Render a label and formatted GBP value."""
        super().__init__(f"{label}: {format_money(amount_pence)}", id=id, classes=classes)
