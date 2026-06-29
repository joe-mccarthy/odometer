"""Simple terminal bar chart widget."""

from collections.abc import Callable

from textual.widgets import Static

from odometer.utils.money import format_money


class SimpleBarChart(Static):
    """Render horizontal bars with ASCII characters."""

    def __init__(
        self,
        title: str,
        rows: list[tuple[str, int]],
        width: int = 32,
        *,
        value_formatter: Callable[[int], str] = format_money,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Create a text-based bar chart with a configurable value formatter."""
        self.title = title
        self.rows = rows
        self.chart_width = width
        self.value_formatter = value_formatter
        super().__init__(self._render_chart(), id=id, classes=classes)

    def update_rows(self, rows: list[tuple[str, int]]) -> None:
        """Update chart rows."""
        self.rows = rows
        self.update(self._render_chart())

    def _render_chart(self) -> str:
        """Render the chart as Rich markup for a Textual Static widget."""
        if not self.rows:
            return f"[b]{self.title}[/b]\nNo data yet."

        maximum = max(amount for _label, amount in self.rows)
        lines = [f"[b]{self.title}[/b]"]
        for label, amount in self.rows:
            size = 0 if maximum == 0 else round((amount / maximum) * self.chart_width)
            bar = "#" * size
            lines.append(f"{label:<8} {bar:<{self.chart_width}} {self.value_formatter(amount)}")
        return "\n".join(lines)
