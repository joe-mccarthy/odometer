"""Shared helpers for rebuilding TUI data tables."""

from collections.abc import Sequence

from textual.widgets import DataTable

TableRow = Sequence[str]


def replace_table_data(
    table: DataTable,
    columns: Sequence[str],
    rows: Sequence[TableRow],
) -> None:
    """Replace table contents and size columns to the loaded data."""
    table.clear(columns=True)
    widths = fitted_column_widths(columns, rows)

    for label, width in zip(columns, widths, strict=True):
        table.add_column(label, width=width)

    for row in rows:
        table.add_row(*row)

    # DataTable normally recalculates virtual dimensions on idle. After a bulk
    # reload, force that pass now so first render has the same fit as a manual refresh.
    new_rows = table._new_rows.copy()
    table._new_rows.clear()
    table._require_update_dimensions = False
    table._update_dimensions(new_rows)
    table.refresh(layout=True)


def fitted_column_widths(columns: Sequence[str], rows: Sequence[TableRow]) -> list[int]:
    """Return display widths that fit every header and cell."""
    widths = [max(_cell_width(column), 1) for column in columns]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], _cell_width(cell), 1)
    return widths


def _cell_width(value: object) -> int:
    """Return the simple display width used by the current ASCII table data."""
    return len(str(value))
