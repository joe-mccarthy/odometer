"""TUI screen tests."""

from odometer.models.enums import ExpenseCategory
from odometer.tui.screens.expenses import expense_category_options


def test_expense_category_options_exclude_fuel() -> None:
    options = expense_category_options()
    values = [value for _, value in options]

    assert ExpenseCategory.FUEL.value not in values
    assert set(values) == {
        category.value for category in ExpenseCategory if category is not ExpenseCategory.FUEL
    }
    assert ("Fine", ExpenseCategory.FINE.value) in options
    assert (ExpenseCategory.MOT.value, ExpenseCategory.MOT.value) in options
