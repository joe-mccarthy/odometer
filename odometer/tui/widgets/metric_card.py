"""Metric card widget."""

from textual.widgets import Static


class MetricCard(Static):
    """A compact metric card."""

    def __init__(
        self,
        label: str,
        value: str,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Render a label and value pair inside a dashboard-style card."""
        super().__init__(f"[b]{label}[/b]\n{value}", id=id, classes=classes)
        self.add_class("metric-card")
