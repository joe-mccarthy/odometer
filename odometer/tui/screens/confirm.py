"""Confirmation modal for destructive TUI actions."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmDeleteModal(ModalScreen[bool]):
    """Confirm a delete action."""

    def __init__(self, title: str, message: str) -> None:
        """Store the title and message shown by the confirmation modal."""
        super().__init__()
        self.confirm_title = title
        self.message = message

    def compose(self) -> ComposeResult:
        """Build the modal with explicit delete and cancel actions."""
        with Container(id="content"):
            yield Static(f"[b]{self.confirm_title}[/b]")
            yield Static(self.message)
            yield Button("Delete", id="delete", variant="error")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle confirmation buttons."""
        self.dismiss(event.button.id == "delete")
