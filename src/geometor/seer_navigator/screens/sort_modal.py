"""Defines the SortModal screen for selecting a DataTable column to sort."""

from typing import Dict, Union, List, Tuple # Added List, Tuple

from textual.app import ComposeResult
from textual.containers import Vertical, Container # Added Container
# Use ModalScreen[ReturnType] to specify what dismiss returns
from textual.screen import ModalScreen
# Import ListView and ListItem, remove Button
from textual.widgets import Label, ListView, ListItem
from textual.binding import Binding
from textual.widgets._data_table import ColumnKey
from textual import log, on # Added on decorator


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

    #dialog > Label { /* Style title label */
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #sort-list { /* Style the ListView */
        border: none;
        background: $surface;
        height: auto; /* Adjust height based on content */
        max-height: 15; /* Limit max height to prevent overflow */
    }

    #sort-list > ListItem {
        padding: 0 1; /* Remove vertical padding, keep horizontal */
        height: 1; /* Explicitly set height to 1 */
    }

    #sort-list > ListItem.--highlight {
        background: $accent;
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
        # Store column labels and their corresponding ColumnKey objects
        self.column_options: List[Tuple[str, ColumnKey]] = []

        for col_key, column_obj in columns.items():
            # Get column label safely
            column_label = "Unknown"
            if hasattr(column_obj, 'label'):
                # Ensure label is extracted correctly, handling potential Text objects
                label_obj = column_obj.label
                if hasattr(label_obj, 'plain'):
                    column_label = label_obj.plain
                else:
                    column_label = str(label_obj) # Fallback to string conversion
            self.column_options.append((column_label, col_key))

        # Sort options alphabetically by label for user convenience
        self.column_options.sort(key=lambda item: item[0])

        log.info(f"SortModal initialized with {len(self.column_options)} column options.")


    def compose(self) -> ComposeResult:
        # Use Container instead of Vertical for more control if needed, but Vertical works
        with Vertical(id="dialog"):
            yield Label("Sort by which column?")
            # Yield the ListView first
            with ListView(id="sort-list"):
                # Yield each ListItem as a child of the ListView
                for label, key in self.column_options:
                    item = ListItem(Label(label))
                    # Store the actual ColumnKey object as a custom attribute on the ListItem
                    item.sort_key = key
                    yield item
            # Consider adding a Cancel button or relying solely on Escape binding
            # yield Button("Cancel", id="cancel", variant="default")


    @on(ListView.Selected)
    def handle_selection(self, event: ListView.Selected) -> None:
        """Handle selection of a column from the ListView."""
        selected_item = event.item
        # Retrieve the stored ColumnKey from the selected ListItem
        if hasattr(selected_item, 'sort_key'):
            selected_key = selected_item.sort_key
            log.info(f"ListView item selected. Dismissing SortModal with ColumnKey: {selected_key}")
            self.dismiss(selected_key) # Dismiss with the selected ColumnKey
        else:
            log.error("Selected ListItem missing 'sort_key' attribute.")
            self.dismiss(None) # Dismiss with None on error

    # Action for the escape binding (remains the same)
    def action_cancel_sort(self) -> None:
        """Called when escape is pressed."""
        log.info("SortModal cancelled via escape key.")
        self.dismiss(None)

