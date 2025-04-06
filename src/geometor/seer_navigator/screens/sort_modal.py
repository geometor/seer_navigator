from typing import Dict

from textual.app import ComposeResult
from textual.containers import Vertical # Changed from Grid
from textual.screen import Screen, ModalScreen # Added ModalScreen
from textual.widgets import Label, Button # Added Button, removed Static
from textual.binding import Binding
from textual.widgets._data_table import ColumnKey
from textual import log


class SortModal(ModalScreen): # Changed base class
    """Modal dialog for selecting a column to sort."""

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
        Binding("escape", "app.pop_screen", "Cancel", show=False),
    ]

    def __init__(
        self,
        parent_screen: Screen,
        columns: Dict[ColumnKey, object],
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.parent_screen = parent_screen
        # Store a mapping from button ID (derived from ColumnKey) to the actual ColumnKey
        self.button_id_to_column_key: Dict[str, ColumnKey] = {}
        self.sortable_columns: Dict[str, str] = {} # Store {button_id: column_label}

        for col_key, column_obj in columns.items():
            # Create a safe button ID from the ColumnKey's underlying string key
            # Access the .key attribute of the ColumnKey object
            column_string_key = col_key.key # Get the actual string key
            button_id = f"sort_btn_{column_string_key}" # Use the string key for the ID
            self.button_id_to_column_key[button_id] = col_key # Store the original ColumnKey object

            # Get column label safely
            column_label = "Unknown"
            if hasattr(column_obj, 'label'):
                column_label = str(column_obj.label.plain) if hasattr(column_obj.label, 'plain') else str(column_obj.label)
            self.sortable_columns[button_id] = column_label

        log.info(f"SortModal initialized for screen: {parent_screen.__class__.__name__}")
        log.info(f"Sortable columns prepared: {self.sortable_columns}")


    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Sort by which column?")
            # Create buttons for each sortable column
            for button_id, column_label in self.sortable_columns.items():
                yield Button(column_label, id=button_id, variant="primary")
            yield Button("Cancel", id="cancel", variant="default") # Add cancel button


    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses for sorting or cancelling."""
        button_id = event.button.id
        log.info(f"Button pressed: {button_id}")

        if button_id == "cancel":
            self.app.pop_screen()
        elif button_id in self.button_id_to_column_key:
            target_key = self.button_id_to_column_key[button_id]
            log.info(f"Attempting to sort by ColumnKey: {target_key}")
            if hasattr(self.parent_screen, "perform_sort"):
                try:
                    self.parent_screen.perform_sort(target_key)
                    self.app.pop_screen() # Close modal after initiating sort
                except Exception as e:
                    log.exception(f"Error calling perform_sort on {self.parent_screen.__class__.__name__}: {e}")
                    self.app.notify(f"Error during sort: {e}", severity="error")
                    self.app.pop_screen() # Close modal even on error
            else:
                log.error(f"Parent screen {self.parent_screen.__class__.__name__} has no perform_sort method.")
                self.app.notify("Sort function not implemented on parent screen.", severity="error")
                self.app.pop_screen()
        else:
            log.error(f"Unknown button ID pressed in SortModal: {button_id}")
            self.app.pop_screen() # Close modal on unknown button

