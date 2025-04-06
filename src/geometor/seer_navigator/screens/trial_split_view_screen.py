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
    """
    A screen that displays trial JSON content side-by-side with the
    rendered TrialViewer grid.
    """

    BINDINGS = [
        Binding("h,escape", "app.pop_screen", "Back", show=True),
        # Add other bindings if needed, e.g., for cycling renderers within this view
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

    # Store the path and renderer type
    trial_path: var[Path | None] = var(None) # Path to the trial.json file
    python_file_path: var[Path | None] = var(None) # Path to the corresponding .py file
    renderer: var[type[Static] | None] = var(None) # Reactive variable, default to None

    def __init__(self, trial_path: Path, renderer_class_arg: type[Static], name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        log.info(f"TrialSplitViewScreen.__init__: Received trial_path: {trial_path}, renderer type: {type(renderer_class_arg)}, value: {renderer_class_arg}")

        # Validate the passed renderer argument
        if not isinstance(renderer_class_arg, type) or not issubclass(renderer_class_arg, Static):
             log.error(f"TrialSplitViewScreen received invalid renderer: {renderer_class_arg}. Falling back to default.")
             from geometor.seer_navigator.renderers.solid_grid import SolidGrid
             renderer_to_use = SolidGrid
        else:
             renderer_to_use = renderer_class_arg

        self.trial_path = trial_path # Store the original trial path for TrialViewer

        # Derive the python file path (assuming '.py.trial.json' structure)
        if trial_path.name.endswith(".py.trial.json"):
            python_filename = trial_path.name[:-len(".trial.json")] # Remove '.trial.json'
            self.python_file_path = trial_path.with_name(python_filename)
            log.info(f"Derived Python file path: {self.python_file_path}")
        else:
            # Handle cases where the naming convention might differ or it's not a .py trial
            log.warning(f"Could not derive Python filename from {trial_path.name}. Displaying trial JSON instead.")
            self.python_file_path = trial_path # Fallback to showing trial JSON if derivation fails

        # Assign the validated class to the reactive variable
        self.renderer = renderer_to_use
        log.info(f"TrialSplitViewScreen.__init__: Set self.renderer to: {self.renderer}")


    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Container(id="json-container"):
                yield TextArea.code_editor(
                    "",
                    read_only=True,
                    show_line_numbers=True,
                    language="python", # Default to python, will be updated in load_content
                    id="code-text-area" # Rename ID for clarity
                )
            with Container(id="trial-viewer-container"):
                # Pass the reactive variable's value (the class) to TrialViewer
                # Ensure self.renderer holds the correct class type here
                if not self.renderer:
                    # Fallback if renderer is somehow None (shouldn't happen after __init__)
                    log.error("TrialSplitViewScreen.compose: self.renderer is None, falling back to SolidGrid for TrialViewer.")
                    from geometor.seer_navigator.renderers.solid_grid import SolidGrid
                    renderer_for_viewer = SolidGrid
                else:
                    renderer_for_viewer = self.renderer

                log.info(f"TrialSplitViewScreen.compose: Instantiating TrialViewer with renderer: {renderer_for_viewer}")
                # Instantiate TrialViewer here, passing the path and validated renderer class
                yield TrialViewer(
                    trial_path=self.trial_path,
                    renderer=renderer_for_viewer, # Pass the class
                    id="trial-viewer-widget"
                )
        yield Footer()

    def on_mount(self) -> None:
        """Load content when the screen is mounted."""
        # Update title based on the file being shown in the text area
        display_file = self.python_file_path if self.python_file_path else self.trial_path
        self.title = f"Code View: {display_file.name}"
        self.load_content()

    def load_content(self) -> None:
        """Loads the Python code (or fallback JSON) into the TextArea and tells TrialViewer to load."""
        code_viewer = self.query_one("#code-text-area", TextArea) # Use updated ID
        trial_viewer = self.query_one("#trial-viewer-widget", TrialViewer)

        # Determine which file to load into the text area
        file_to_load = self.python_file_path
        language = "python"
        if not file_to_load or not file_to_load.is_file():
            log.warning(f"Python file {self.python_file_path} not found. Falling back to trial JSON {self.trial_path}.")
            file_to_load = self.trial_path # Fallback to trial path
            language = "json" # Set language to json for fallback

        # Check if the final file_to_load exists
        if not file_to_load or not file_to_load.is_file():
            error_msg = f"Error: Neither Python file nor Trial file found.\nPython attempt: {self.python_file_path}\nTrial file: {self.trial_path}"
            log.error(error_msg)
            code_viewer.load_text(error_msg)
            code_viewer.language = None
            self.app.notify("Error: Could not load file content.", severity="error")
            # Optionally clear TrialViewer or show error state
            # trial_viewer.clear() # Assuming TrialViewer has a clear method
            return

        # Load content into the text area
        try:
            content = file_to_load.read_text()
            code_viewer.load_text(content)
            code_viewer.language = language
            code_viewer.scroll_home(animate=False)
            log.info(f"Loaded {file_to_load.name} into text area.")
        except Exception as e:
            log.error(f"Error loading file {file_to_load} into text area: {e}")
            error_msg = f"Error loading file:\n{file_to_load.name}\n\n{e}"
            code_viewer.load_text(error_msg)
            code_viewer.language = None
            self.app.notify(f"Error loading file: {e}", severity="error")

        # Load TrialViewer using the original trial_path (regardless of text area content)
        if self.trial_path and self.trial_path.is_file():
            # Path and renderer are already set during __init__ and passed to yield
            # We just need to trigger its loading mechanism if it doesn't load automatically on mount
            # (TrialViewer's on_mount should call load_and_display)
            # If TrialViewer needs an explicit call after mount:
            try:
                # TrialViewer's on_mount should handle its loading if path/renderer are set
                # If explicit loading is needed after mount/path change:
                trial_viewer.load_and_display()
                log.info(f"Triggered TrialViewer load for {self.trial_path.name}.")
            except Exception as e:
                 log.error(f"Error loading TrialViewer for {self.trial_path}: {e}")
                 self.app.notify(f"Error loading grid view: {e}", severity="error")
                 # Optionally display an error within the TrialViewer widget itself
        else:
            log.error(f"Trial file {self.trial_path} not found for TrialViewer.")
            # Optionally clear TrialViewer or show error state
            # trial_viewer.clear()


    # --- Renderer Cycling Actions ---
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
            # Update the renderer_class attribute within the TrialViewer instance
            trial_viewer.renderer_class = new_renderer_class
            # Trigger a refresh of the TrialViewer's display
            trial_viewer.refresh_display()
            self.app.notify(f"Renderer set to: {renderer_name.capitalize()}")
        else:
            log.warning(f"Unknown renderer name: {renderer_name}")
            self.app.notify(f"Unknown renderer: {renderer_name}", severity="warning")
