"""Defines the StepScreen for browsing files within a task step."""

from pathlib import Path
import subprocess
import shutil # To find terminal emulator


from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Header, Footer, TextArea, ContentSwitcher, Static # Removed Markdown
from textual.binding import Binding
from textual import log

# Import the new screen we will create
from geometor.seer_navigator.screens.trial_split_view_screen import TrialSplitViewScreen


LANGUAGE_MAP = {
    ".py": "python",
    ".md": "markdown", 
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".txt": None,
}
# DEFAULT_THEME = "" # Removed unused variable

class StepScreen(Screen):
    """Displays the files within a step folder and their content."""

    CSS = """
    Screen {
        layers: base overlay;
    }

    Horizontal {
        height: 1fr;
    }

    #file-list-container {
        width: 30%;
        border-right: thick $accent;
        height: 1fr;
        overflow-y: auto; /* Ensure DataTable scrolls if needed */
    }

    #file-content-container {
        width: 70%;
        height: 1fr;
    }

    DataTable {
       height: 100%; /* Make DataTable fill its container */
       width: 100%;
    }

    /* Ensure ContentSwitcher and its children fill the container */
    ContentSwitcher {
        height: 1fr;
    }
    TextArea, #content-placeholder {
        height: 1fr;
        border: none; /* Remove default border if desired */
    }
    /* Center placeholder text */
    #content-placeholder {
        content-align: center middle;
        color: $text-muted;
    }


    /* Style the focused row in the DataTable */
    DataTable > .datatable--cursor {
        background: $accent;
        color: $text;
    }
    DataTable:focus > .datatable--cursor {
         background: $accent-darken-1;
    }

    """

    BINDINGS = [
        Binding("j", "cursor_down", "Cursor Down", show=False),
        Binding("k", "cursor_up", "Cursor Up", show=False),
        Binding("enter", "select_file", "Select File", show=False), 
        Binding("h", "app.pop_screen", "Back", show=True),
        Binding("r", "open_terminal", "Open Terminal", show=True), 
        Binding("v", "view_trial_split", "View Trial Split", show=True), # Added binding
        # REMOVED Binding("i", "view_images", "View Images", show=True),
        # Binding("[", "previous_sibling", "Previous Sibling", show=True), 
        # Binding("]", "next_sibling", "Next Sibling", show=True),     
    ]

    # Reactive variable to store the list of files
    file_paths = reactive([])
    selected_file_path = reactive(None)

    def __init__(self, session_path: Path, task_path: Path, step_path: Path) -> None:
        super().__init__()
        self.session_path = session_path
        self.task_path = task_path
        self.step_path = step_path
        self.step_name = step_path.name
        self.task_name = task_path.name
        self.session_name = session_path.name

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="file-list-container"):
                yield DataTable(id="file-list-table")
            with Vertical(id="file-content-container"):
                with ContentSwitcher(initial="text-viewer"):
                    yield TextArea.code_editor(
                        "",
                        read_only=True,
                        show_line_numbers=True,
                        soft_wrap=True, # Enable soft wrapping
                        #  theme=DEFAULT_THEME,
                        id="text-viewer" # ID for the TextArea
                    )
                    # Removed TrialViewer from here
                    yield Static("Select a file to view its content.", id="content-placeholder")

        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.title = f"{self.session_name} • {self.task_name} • {self.step_name}"

        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("Files", width=None) # Let width be automatic

        # List files in the step directory, sorted alphabetically
        try:
            # Filter for files only, ignore directories
            self.file_paths = sorted([f for f in self.step_path.iterdir() if f.is_file()])
        except FileNotFoundError:
            self.app.pop_screen() # Go back if path doesn't exist
            self.app.notify("Error: Step directory not found.", severity="error")
            return
        except Exception as e:
            log.error(f"Error listing files in {self.step_path}: {e}")
            self.app.pop_screen()
            self.app.notify(f"Error listing files: {e}", severity="error")
            return

        if not self.file_paths:
            table.add_row("No files found.")
            # Disable table focus if empty? Or allow focus but handle selection gracefully.
        else:
            for file_path in self.file_paths:
                table.add_row(file_path.name)

            self.select_row_index(0)
            table.focus() 

    def select_row_index(self, index: int):
        """Selects a row by index and triggers loading/display logic."""
        if 0 <= index < len(self.file_paths):
            table = self.query_one(DataTable)
            # Check if cursor is already at the target row to avoid unnecessary updates
            if table.cursor_row != index:
                table.move_cursor(row=index, animate=False)
            # Update selected_file_path which triggers the watch method
            self.selected_file_path = self.file_paths[index]
        else:
            self.selected_file_path = None # Clear selection if index is out of bounds

    # Watch for changes in selected_file_path and update the appropriate viewer
    def watch_selected_file_path(self, old_path: Path | None, new_path: Path | None) -> None:
        """Called when selected_file_path changes. Updates the content viewer."""
        switcher = self.query_one(ContentSwitcher)
        text_viewer = self.query_one("#text-viewer", TextArea)
        placeholder = self.query_one("#content-placeholder", Static)

        if new_path:
            file_suffix = new_path.suffix.lower()
            file_name = new_path.name

            # Check if it's a trial file - treat like other text files now
            # The special handling is moved to action_view_trial_split
            if file_name.endswith("trial.json") or file_name.endswith("trials.json"):
                log.info(f"Displaying JSON content for: {new_path}")
                try:
                    content = new_path.read_text()
                    text_viewer.load_text(content)
                    text_viewer.language = "json" # Set language to JSON
                    switcher.current = "text-viewer"
                    text_viewer.scroll_home(animate=False)
                except Exception as e:
                    log.error(f"Error loading trial JSON file {new_path}: {e}")
                    error_content = f"Error loading file:\n\n{e}"
                    text_viewer.load_text(error_content)
                    text_viewer.language = None
                    switcher.current = "text-viewer"

            elif file_suffix == ".png":
                # Handle PNG files - show placeholder
                placeholder.update(f"Selected: '{new_path.name}' (PNG)\n\nPress 'i' to view images (if available).") # Updated placeholder text
                switcher.current = "content-placeholder"

            elif file_suffix == ".md":
                # Handle Markdown files using TextArea
                try:
                    content = new_path.read_text()
                    # Load into TextArea and set language
                    text_viewer.load_text(content)
                    text_viewer.language = "markdown"
                    switcher.current = "text-viewer"
                    text_viewer.scroll_home(animate=False) # Scroll TextArea to top
                except Exception as e:
                    log.error(f"Error loading Markdown file {new_path}: {e}")
                    # Display error in TextArea (fallback)
                    error_content = f"Error loading file:\n\n{e}"
                    text_viewer.load_text(error_content)
                    text_viewer.language = None
                    switcher.current = "text-viewer"

            else:
                # Handle other text/code files
                try:
                    content = new_path.read_text()
                    language = LANGUAGE_MAP.get(file_suffix)

                    # Check if language requires the 'syntax' extra for TextArea
                    if language and language not in text_viewer.available_languages:
                         log.warning(f"Language '{language}' for {new_path.name} not available in TextArea. Install 'textual[syntax]' for highlighting.")
                         language = None # Fallback for TextArea

                    # Load text first, then set language for TextArea
                    text_viewer.load_text(content)
                    text_viewer.language = language
                    switcher.current = "text-viewer"
                    text_viewer.scroll_home(animate=False) # Scroll TextArea to top
                except Exception as e:
                    log.error(f"Error loading file {new_path}: {e}")
                    # Display error in TextArea
                    error_content = f"Error loading file:\n\n{e}"
                    text_viewer.load_text(error_content)
                    text_viewer.language = None
                    switcher.current = "text-viewer"

        else:
            # Clear viewer if no file is selected
            text_viewer.load_text("")
            text_viewer.language = None
            placeholder.update("No file selected.") # Reset placeholder
            # Switch to placeholder when nothing is selected
            switcher.current = "content-placeholder"


    def action_cursor_down(self) -> None:
        """Move the cursor down in the DataTable."""
        table = self.query_one(DataTable)
        current_row = table.cursor_row
        next_row = min(len(self.file_paths) - 1, current_row + 1)
        self.select_row_index(next_row) # Use select_row_index to trigger watch

    def action_cursor_up(self) -> None:
        """Move the cursor up in the DataTable."""
        table = self.query_one(DataTable)
        current_row = table.cursor_row
        prev_row = max(0, current_row - 1)
        self.select_row_index(prev_row) # Use select_row_index to trigger watch

    def action_select_file(self) -> None:
        """Action triggered by pressing Enter on the table."""
        # The watch_selected_file_path handles pushing TrialScreen or updating viewers.
        # This action might be useful if we want Enter to *always* try to open/view,
        # even if the selection hasn't changed, but for now, it's implicitly handled.
        # We could force a re-evaluation if needed:
        current_path = self.selected_file_path
        if current_path:
             # Temporarily set to None and back to force the watch method
             # This ensures the watch method runs even if the selection didn't change visually
             self.selected_file_path = None
             self.selected_file_path = current_path
        pass # Corrected indentation

    def action_view_trial_split(self) -> None:
        """Finds all trial files in the current step and pushes TrialSplitViewScreen."""
        try:
            trial_files = sorted([
                f for f in self.step_path.iterdir()
                if f.is_file() and (f.name.endswith(".trial.json") or f.name.endswith("trials.json"))
            ])

            if not trial_files:
                self.app.notify("No '.trial.json' files found in this step.", severity="warning")
                return

            log.info(f"Found {len(trial_files)} trial files in step {self.step_name}. Pushing TrialSplitViewScreen.")
            split_screen = TrialSplitViewScreen(
                trial_paths=trial_files, # Pass the list of paths
                renderer_class_arg=self.app.renderer # Pass the app's current renderer class
            )
            self.app.push_screen(split_screen)

        except FileNotFoundError:
             self.app.notify("Step directory not found.", severity="error")
             log.error(f"Step directory not found when searching for trials: {self.step_path}")
        except Exception as e:
             self.app.notify(f"Error finding trial files: {e}", severity="error")
             log.error(f"Error finding trial files in {self.step_path}: {e}")


    def action_open_terminal(self) -> None:
        """Opens a new terminal window in the current step directory."""
        # Corrected indentation for the whole method body
        terminal_commands = [
            "gnome-terminal",
            "konsole",
             "xfce4-terminal",
             "lxterminal",
             "mate-terminal",
             "terminator",
             "xterm",
             # Add other common Linux terminals if needed
        ]
        terminal_cmd = None
        for cmd in terminal_commands:
            if shutil.which(cmd):
                terminal_cmd = cmd
                break

        if not terminal_cmd:
            # Basic fallback for macOS (might need refinement)
            if shutil.which("open"):
                 try:
                     # Use 'open -a Terminal .' which should open Terminal.app at the CWD
                     subprocess.Popen(["open", "-a", "Terminal", "."], cwd=self.step_path)
                     log.info(f"Opened macOS Terminal in {self.step_path}")
                     return # Success
                 except Exception as e:
                     log.error(f"Failed to open macOS Terminal: {e}")
                     # Fall through to notify error if 'open' failed
 
            log.error("Could not find a suitable terminal emulator.")
            self.app.notify("Could not find a suitable terminal emulator.", severity="error")
            return
 
        try:
            log.info(f"Opening terminal '{terminal_cmd}' in {self.step_path}")
            # Most terminals accept --working-directory= or similar, but launching
            # with cwd set in Popen is more reliable across different terminals.
            subprocess.Popen([terminal_cmd], cwd=self.step_path)
        except Exception as e:
            log.error(f"Failed to open terminal {terminal_cmd}: {e}")
            self.app.notify(f"Failed to open terminal: {e}", severity="error")
 
 
    # Removed action_view_images as the binding was removed.
    # If you want to keep the functionality but trigger it differently, let me know.

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the DataTable (e.g., by clicking)."""
        # Corrected indentation for the whole method body
        # Ensure the index is valid before selecting
        if event.cursor_row is not None and 0 <= event.cursor_row < len(self.file_paths):
            # Use select_row_index to trigger the watch method consistently
            self.select_row_index(event.cursor_row)
        else:
            self.selected_file_path = None # Clear if selection is invalid

    def refresh_content(self) -> None:
        """Reloads the file list and the content of the selected file."""
        log.info(f"Refreshing StepScreen content for {self.step_path.name}...")
        table = self.query_one(DataTable)
        current_cursor_row = table.cursor_row
        previously_selected_filename = self.selected_file_path.name if self.selected_file_path else None

        # Re-list files
        try:
                self.file_paths = sorted([f for f in self.step_path.iterdir() if f.is_file()])
        except Exception as e:
            log.error(f"Error re-listing files in {self.step_path}: {e}")
            self.app.notify(f"Error refreshing file list: {e}", severity="error")
            # Optionally clear table or show error state
            table.clear()
            table.add_row("Error refreshing list.")
            self.selected_file_path = None # Clear selection
            return

        # Clear and repopulate table
        table.clear()
        if not self.file_paths:
            table.add_row("No files found.")
            self.selected_file_path = None # Clear selection
        else:
            for file_path in self.file_paths:
                table.add_row(file_path.name)

            # Try to re-select the previously selected file by name
            new_index = -1
            if previously_selected_filename:
                try:
                    new_index = [f.name for f in self.file_paths].index(previously_selected_filename)
                except ValueError:
                    new_index = -1 # File no longer exists

            # Select the found index, or the previous row index if valid, or the first row
            if new_index != -1:
                self.select_row_index(new_index)
            elif current_cursor_row is not None and 0 <= current_cursor_row < len(self.file_paths):
                self.select_row_index(current_cursor_row) # Fallback to previous index if still valid
            else:
                self.select_row_index(0) # Fallback to first item

        table.focus() # Ensure table has focus
