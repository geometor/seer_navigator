"""Defines the ImageViewModal screen for selecting image viewing filters."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, Footer, Header, Label, Static
from textual.binding import Binding # Added Binding
from textual import log


#  class ImageViewModal(Screen):
class ImageViewModal(ModalScreen):
    """Screen with a dialog to select image view filters."""

    CSS = """
ImageViewModal {
    align: center middle;
}

#dialog {
    padding: 0 1;
    width: 60;
    height: 20;
    border: thick $background 80%;
    background: $surface;
}

#question {
    column-span: 2;
    height: 1fr;
    width: 1fr;
    content-align: center middle;
}

Button {
    width: 100%;
}
"""

    BINDINGS = [
        Binding("a", "select_filter('all')", "All", show=False),
        Binding("t", "select_filter('tasks')", "Tasks", show=False),
        Binding("r", "select_filter('trials')", "Trials", show=False),
        Binding("p", "select_filter('passed_trials')", "Passed Trials", show=False), # ADDED binding
        Binding("escape", "app.pop_screen", "Cancel", show=False),
    ]

    def __init__(self, context_path: Path, task_id: str | None = None, *args, **kwargs) -> None: # Added task_id
        super().__init__(*args, **kwargs)
        self.context_path = context_path
        self.task_id = task_id # Store task_id
        log.info(f"ImageViewModal initialized with context: {self.context_path}, task_id: {self.task_id}")

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Select images to view:", id="question"),
            Static(f"Context: {self.context_path}", id="context-label"),
            # Conditionally display Task ID
            *([Static(f"Task: {self.task_id}", id="task-label")] if self.task_id else []),
            Button("All (.png)", variant="primary", id="all"),
            Button("Tasks (task.png)", variant="primary", id="tasks"),
            Button("Trials (*trial.png)", variant="primary", id="trials"),
            Button("Passed Trials (*trial.png)", variant="success", id="passed_trials"), # ADDED button
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        filter_type = event.button.id
        if filter_type == "cancel":
            self.app.pop_screen()
        else:
            # Call the launch method on the main app
            try:
                # Check if the app has the launch_sxiv method
                if hasattr(self.app, "launch_sxiv"):
                    log.info(f"Calling launch_sxiv with context={self.context_path}, filter='{filter_type}', task_id='{self.task_id}'")
                    # Pass task_id to launch_sxiv
                    self.app.launch_sxiv(self.context_path, filter_type, self.task_id)
                else:
                    log.error("App does not have launch_sxiv method.")
                    self.app.notify("Error: Image launch function not found.", severity="error")
            except Exception as e:
                 log.error(f"Error calling launch_sxiv: {e}")
                 self.app.notify(f"Error launching image viewer: {e}", severity="error")
            finally:
                self.app.pop_screen() # Close modal regardless of success/failure

    def action_select_filter(self, filter_type: str) -> None:
        """Called by key bindings."""
        log.info(f"Filter '{filter_type}' selected via key binding.")
        # Simulate button press to reuse the logic
        button = self.query_one(f"#{filter_type}", Button)
        self.on_button_pressed(Button.Pressed(button))

