from pathlib import Path
# import json # Removed unused import

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container # Use Container for flexible sizing
from textual.reactive import var
from textual.screen import Screen
from textual.widgets import Header, Footer, TextArea, Static
from textual import log

# Import the TrialViewer widget which will handle the grid rendering
from geometor.seer_navigator.screens.trial_screen import TrialViewer
# Import a default renderer if needed, or rely on the one passed from the app
from geometor.seer_navigator.renderers.solid_grid import SolidGrid

class TrialSplitViewScreen(Screen):
    A screen that displays Python source code side-by-side with the
    rendered TrialViewer grid for a set of trials, allowing navigation between them.
    """

    BINDINGS = [
        Binding("h,escape,q", "app.pop_screen", "Back", show=True),
        Binding("j,down", "next_trial", "Next Trial", show=True),
        Binding("k,up", "previous_trial", "Previous Trial", show=True),
        Binding("ctrl+s", "set_renderer('solid')", "Solid", show=False),
        Binding("ctrl+c", "set_renderer('char')", "Char", show=False),
        Binding("ctrl+b", "set_renderer('block')", "Block", show=False),
        Binding("ctrl+t", "set_renderer('tiny')", "Tiny", show=False),
    ]

    CSS = """
    TrialSplitViewScreen > Horizontal {
        height: 1fr; /* Make horizontal fill the screen */
    }

    #json-container {
        width: 50%;
        border-right: thick $accent;
        height: 1fr;
    }

    #trial-viewer-container {
        width: 50%;
        height: 1fr;
    }

    /* Ensure children fill their containers */
    #json-text-area {
        height: 1fr;
        border: none;
    }
    #trial-viewer-widget {
       /* TrialViewer is scrollable, let it manage its own height/scrolling */
       height: 1fr;
    }
    """

    # Store the list of trial paths and current index
    trial_paths: var[list[Path]] = var([])
    current_index: var[int] = var(0)
    # Store the derived python path for the *current* trial
    current_python_path: var[Path | None] = var(None)
    # Store the renderer class
    renderer: var[type[Static] | None] = var(None)

    def __init__(self, trial_paths: list[Path], renderer_class_arg: type[Static], name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        log.info(f"TrialSplitViewScreen.__init__: Received {len(trial_paths)} trial paths. Renderer: {renderer_class_arg}")

        if not trial_paths:
            log.error("TrialSplitViewScreen initialized with no trial paths!")
            # Handle this case gracefully, maybe pop screen or show error message
            self.trial_paths = []
            # Consider popping the screen immediately or showing an error static widget
            # self.app.pop_screen()
            # self.app.notify("No trial files found to view.", severity="error", timeout=5)

        self.trial_paths = trial_paths # Store the list

        # Validate and store the renderer class
        if not isinstance(renderer_class_arg, type) or not issubclass(renderer_class_arg, Static):
             log.error(f"TrialSplitViewScreen received invalid renderer: {renderer_class_arg}. Falling back to SolidGrid.")
             from geometor.seer_navigator.renderers.solid_grid import SolidGrid
             self.renderer = SolidGrid
        else:
             self.renderer = renderer_class_arg

        # Initial setup will be handled by watch_current_index or on_mount calling load_current_trial
        # self.current_index is already 0 by default

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Container(id="json-container"):
                yield TextArea.code_editor(
                    "",
                    read_only=True,
                    show_line_numbers=True,
                    language="python", # Default to python, will be updated in load_content
                    id="code-text-area" # Keep ID
                )
            with Container(id="trial-viewer-container"):
                # Instantiate TrialViewer here. It will be configured by load_current_trial
                # Pass the initial renderer class. Path will be set dynamically.
                yield TrialViewer(
                    trial_path=None, # Initial path is None, set by load_current_trial
                    renderer=self.renderer, # Pass the class stored on the screen
                    id="trial-viewer-widget"
                )
        yield Footer()

    def on_mount(self) -> None:
        """Load the initial trial content when the screen is mounted."""
        if not self.trial_paths:
             # If initialized with no paths, show error and potentially pop
             self.query_one("#code-text-area", TextArea).load_text("Error: No trial files were provided.")
             self.app.notify("No trial files found to view.", severity="error", timeout=5)
             # Consider adding a placeholder to the TrialViewer side as well
             # self.app.call_later(self.app.pop_screen, delay=1.0) # Optionally auto-close
             return
        self.load_current_trial() # Load content for index 0

    def watch_current_index(self, old_index: int, new_index: int) -> None:
        """Called when current_index changes. Reloads the content."""
        log.debug(f"Index changed from {old_index} to {new_index}. Reloading trial.")
        if 0 <= new_index < len(self.trial_paths):
            self.load_current_trial()
        else:
            log.error(f"Attempted to switch to invalid index: {new_index}")
            # Optionally reset index or show error
            self.current_index = old_index # Revert to old index

    def _derive_python_path(self, trial_path: Path) -> Path | None:
        """Derives the corresponding python file path from a trial path."""
        if trial_path.name.endswith(".py.trial.json"):
            python_filename = trial_path.name[:-len(".trial.json")]
            py_path = trial_path.with_name(python_filename)
            log.debug(f"Derived Python path {py_path} from {trial_path}")
            return py_path
        else:
            log.warning(f"Could not derive Python filename from {trial_path.name}. Cannot display source.")
            return None

    def load_current_trial(self) -> None:
        """Loads the Python code and TrialViewer grid for the current index."""
        if not self.trial_paths or not (0 <= self.current_index < len(self.trial_paths)):
            log.error(f"load_current_trial called with invalid index {self.current_index} or empty paths.")
            return

        current_trial_path = self.trial_paths[self.current_index]
        self.current_python_path = self._derive_python_path(current_trial_path)

        # Update Title
        total_trials = len(self.trial_paths)
        display_name = self.current_python_path.name if self.current_python_path else current_trial_path.name
        self.title = f"Trial ({self.current_index + 1}/{total_trials}): {display_name}"

        # --- Load Code into TextArea ---
        code_viewer = self.query_one("#code-text-area", TextArea)
        if self.current_python_path and self.current_python_path.is_file():
            try:
                content = self.current_python_path.read_text()
                code_viewer.load_text(content)
                code_viewer.language = "python"
                code_viewer.scroll_home(animate=False)
                log.info(f"Loaded code from {self.current_python_path.name}")
            except Exception as e:
                log.error(f"Error loading Python file {self.current_python_path}: {e}")
                code_viewer.load_text(f"# Error loading file:\n# {self.current_python_path.name}\n\n{e}")
                code_viewer.language = None
        elif self.current_python_path:
            # Derived path exists but file doesn't
             log.warning(f"Python file not found: {self.current_python_path}")
             code_viewer.load_text(f"# Python file not found:\n# {self.current_python_path.name}")
             code_viewer.language = None
        else:
            # Could not derive python path
            code_viewer.load_text(f"# Could not determine Python source for:\n# {current_trial_path.name}")
            code_viewer.language = None


        # --- Load Grid into TrialViewer ---
        trial_viewer = self.query_one("#trial-viewer-widget", TrialViewer)
        if current_trial_path.is_file():
            try:
                # Update the path and renderer class on the existing TrialViewer instance
                trial_viewer.trial_path = current_trial_path
                trial_viewer.renderer = self.renderer # Ensure it has the correct class
                trial_viewer.load_and_display() # Tell it to reload based on new path/renderer
                log.info(f"Loaded trial grid from {current_trial_path.name}")
            except Exception as e:
                 log.error(f"Error loading TrialViewer for {current_trial_path}: {e}")
                 self.app.notify(f"Error loading grid view: {e}", severity="error")
                 # Optionally display an error within the TrialViewer widget itself (e.g., clear it)
                 # trial_viewer.clear_display() # Assuming such a method exists
        else:
            log.error(f"Trial file {current_trial_path} not found for TrialViewer.")
            # Optionally clear TrialViewer or show error state
            # trial_viewer.clear_display()

    def action_next_trial(self) -> None:
        """Go to the next trial in the list."""
        if self.current_index < len(self.trial_paths) - 1:
            self.current_index += 1
        else:
            self.app.bell() # Optional feedback

    def action_previous_trial(self) -> None:
        """Go to the previous trial in the list."""
        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.app.bell() # Optional feedback

    # --- Renderer Cycling Actions --- (Keep as is, but ensure TrialViewer uses self.renderer)
    # These actions allow changing the renderer within the split view
    def action_set_renderer(self, renderer_name: str) -> None:
        """Sets the grid renderer type for the TrialViewer."""
        # Map name to actual class (similar to how SessionsNavigator might do it)
        # You might need to import these at the top
        from geometor.seer_navigator.renderers import SolidGrid, CharGrid, BlockGrid, TinyGrid
        renderer_map = {
            "solid": SolidGrid,
            "char": CharGrid,
            "block": BlockGrid,
            "tiny": TinyGrid,
        }
        new_renderer_class = renderer_map.get(renderer_name)

        if new_renderer_class:
            log.info(f"Setting renderer to {renderer_name}")
            self.renderer = new_renderer_class # Update the screen's reactive var
            trial_viewer = self.query_one("#trial-viewer-widget", TrialViewer)
            # Update the 'renderer' attribute (which holds the class) within the TrialViewer instance
            trial_viewer.renderer = new_renderer_class
            # Trigger a refresh of the TrialViewer's display
            trial_viewer.refresh_display()
            self.app.notify(f"Renderer set to: {renderer_name.capitalize()}")
        else:
            log.warning(f"Unknown renderer name: {renderer_name}")
            self.app.notify(f"Unknown renderer: {renderer_name}", severity="warning")
