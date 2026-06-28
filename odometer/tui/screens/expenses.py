"""Expenses screen."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from odometer.models.enums import ExpenseCategory
from odometer.services.exceptions import OdometerError
from odometer.tui.app import OdometerTUI
from odometer.utils.formatting import format_optional_int
from odometer.utils.money import MoneyParseError, format_money


def expense_category_label(category: ExpenseCategory) -> str:
    """Return a display label for an expense category."""
    if category is ExpenseCategory.MOT:
        return category.value
    return category.value.replace("_", " ").title()


def expense_category_options() -> list[tuple[str, str]]:
    """Return non-fuel expense category options for the TUI form."""
    return [
        (expense_category_label(category), category.value)
        for category in ExpenseCategory
        if category is not ExpenseCategory.FUEL
    ]


class ExpensesScreen(Screen[None]):
    """Expense table screen."""

    BINDINGS = [
        ("a", "add_expense", "Add"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("[b]Expenses[/b]", classes="section")
            yield Static("", id="message")
            yield DataTable(id="expenses-table")
        yield Footer()

    def on_mount(self) -> None:
        """Populate table."""
        self.refresh_table()

    def refresh_table(self) -> None:
        """Refresh expenses."""
        app = cast(OdometerTUI, self.app)
        rows = app.get_expenses()
        table = self.query_one("#expenses-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Vehicle", "Category", "Amount", "Mileage", "Description")
        if not rows:
            self.query_one("#message", Static).update("No expenses found.")
            return
        self.query_one("#message", Static).update("")
        for row in rows:
            expense = row.expense
            table.add_row(
                expense.date.isoformat(),
                row.registration,
                expense.category.value,
                format_money(expense.amount_pence),
                format_optional_int(expense.odometer_miles),
                expense.description or "-",
            )

    def action_refresh(self) -> None:
        """Refresh table."""
        self.refresh_table()

    def on_screen_resume(self) -> None:
        """Refresh after returning to this screen."""
        if self.is_mounted:
            self.refresh_table()

    def action_add_expense(self) -> None:
        """Open add expense modal."""
        self.app.push_screen(AddExpenseModal(), callback=self._after_add)

    def _after_add(self, saved: bool | None) -> None:
        if saved:
            self.refresh_table()


class AddExpenseModal(ModalScreen[bool]):
    """Simple add expense form."""

    def compose(self) -> ComposeResult:
        with Container(id="content"):
            yield Static("[b]Add expense[/b]")
            yield Input(placeholder="Vehicle registration or id", id="vehicle")
            yield Select(
                expense_category_options(),
                prompt="Category",
                allow_blank=False,
                value=ExpenseCategory.SERVICE.value,
                id="category",
            )
            yield Input(placeholder="Amount", id="amount")
            yield Input(placeholder="Date yyyy-mm-dd", id="date")
            yield Input(placeholder="Mileage", id="mileage")
            yield Input(placeholder="Description", id="description")
            yield Static("", id="message")
            yield Button("Save", id="save", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle buttons."""
        if event.button.id == "cancel":
            self.dismiss(False)
            return
        try:
            app = cast(OdometerTUI, self.app)
            app.add_expense_from_form(
                {
                    "vehicle": self.query_one("#vehicle", Input).value,
                    "category": str(self.query_one("#category", Select).value),
                    "amount": self.query_one("#amount", Input).value,
                    "date": self.query_one("#date", Input).value,
                    "mileage": self.query_one("#mileage", Input).value,
                    "description": self.query_one("#description", Input).value,
                }
            )
        except (OdometerError, MoneyParseError, ValueError) as exc:
            self.query_one("#message", Static).update(str(exc))
            return
        self.dismiss(True)
