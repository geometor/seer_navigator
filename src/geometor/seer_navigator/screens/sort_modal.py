from typing import Dict, Union # Added Union

from textual.app import ComposeResult
from textual.containers import Vertical
# Use ModalScreen[ReturnType] to specify what dismiss returns
from textual.screen import ModalScreen
from textual.widgets import Label, Button
from textual.binding import Binding
from textual.widgets._data_table import ColumnKey
from textual import log


# Specify the return type for dismiss()
class SortModal(ModalScreen[Union[ColumnKey, None]]):
    """Modal dialog for selecting a column to sort. Returns the selected ColumnKey or None."""

    CSS = """
    SortModal {
        align: center middle;
    }

    #dialog { /* Changed ID and styling */
        padding: 0 1;
        width: auto; /* Auto width based on content */
        max-width: 60; /* Limit max width */
        height: auto; /* Auto height based on content */
        max-height: 80%; /* Limit max height */
        border: thick $background 80%;
        background: $surface;
    }

    #dialog > Label { /* Style label */
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #dialog > Button { /* Style buttons */
        width: 100%;
        margin-top: 1; /* Add space between buttons */
    }
    """

    BINDINGS = [
        Binding("escape", "cancel_sort", "Cancel", show=False), # Changed action
    ]

    # Remove parent_screen from __init__
    def __init__(
        self,
        columns: Dict[ColumnKey, object],
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        # self.parent_screen = parent_screen # REMOVED
        # Store a mapping from button ID (derived from ColumnKey) to the actual ColumnKey
        self.button_id_to_column_key: Dict[str, ColumnKey] = {}
        self.sortable_columns: Dict[str, str] = {} # Store {button_id: column_label}

        for col_key, column_obj in columns.items():
            # Create a safe button ID from the ColumnKey's underlying string key
            # Convert the ColumnKey object to its string representation
            column_string_key = str(col_key) # Get the string representation of the ColumnKey
            button_id = f"sort_btn_{column_string_key}" # Use the string key for the ID
            self.button_id_to_column_key[button_id] = col_key # Store the original ColumnKey object

            # Get column label safely
            column_label = "Unknown"
            if hasattr(column_obj, 'label'):
                column_label = str(column_obj.label.plain) if hasattr(column_obj.label, 'plain') else str(column_obj.label)
            self.sortable_columns[button_id] = column_label

        # Removed log line referencing parent_screen as it's no longer passed
        log.info(f"Sortable columns prepared: {self.sortable_columns}")


    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Sort by which column?")
            # Create buttons for each sortable column
            for button_id, column_label in self.sortable_columns.items():
                yield Button(column_label, id=button_id, variant="primary")
            yield Button("Cancel", id="cancel", variant="default") # Add cancel button


    # Use dismiss() instead of pop_screen() and calling parent
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses, dismissing the modal with the result."""
        button_id = event.button.id
        log.info(f"Button pressed: {button_id}")

        if button_id == "cancel":
            self.dismiss(None) # Dismiss with None for cancellation
        elif button_id in self.button_id_to_column_key:
            target_key = self.button_id_to_column_key[button_id]
            log.info(f"Dismissing SortModal with ColumnKey: {target_key}")
            self.dismiss(target_key) # Dismiss with the selected ColumnKey
        else:
            log.error(f"Unknown button ID pressed in SortModal: {button_id}")
            self.dismiss(None) # Dismiss with None on error/unknown button

    # Action for the escape binding
    def action_cancel_sort(self) -> None:
        """Called when escape is pressed."""
        log.info("SortModal cancelled via escape key.")
        self.dismiss(None)

