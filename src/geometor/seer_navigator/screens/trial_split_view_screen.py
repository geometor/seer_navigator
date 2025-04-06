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
    trial_path = var(None)
    renderer = var(SolidGrid) # Default renderer

    def __init__(self, trial_path: Path, renderer: type[Static], name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.trial_path = trial_path
        self.renderer = renderer # Store the renderer passed from the app

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Container(id="json-container"):
                yield TextArea.code_editor(
                    "",
                    read_only=True,
                    show_line_numbers=True,
                    language="json",
                    id="json-text-area"
                )
            with Container(id="trial-viewer-container"):
                # Instantiate TrialViewer here, passing the path and renderer
                yield TrialViewer(
                    trial_path=self.trial_path,
                    renderer=self.renderer,
                    id="trial-viewer-widget"
                )
        yield Footer()

    def on_mount(self) -> None:
        """Load content when the screen is mounted."""
        self.title = f"Trial View: {self.trial_path.name}"
        self.load_content()

    def load_content(self) -> None:
        """Loads the JSON into the TextArea and tells TrialViewer to load."""
        json_viewer = self.query_one("#json-text-area", TextArea)
        trial_viewer = self.query_one("#trial-viewer-widget", TrialViewer)

        if not self.trial_path or not self.trial_path.is_file():
            log.error(f"Trial file not found or invalid: {self.trial_path}")
            json_viewer.load_text(f"Error: Trial file not found\n{self.trial_path}")
            # Optionally clear or show an error in TrialViewer as well
            self.app.notify(f"Error: Trial file not found: {self.trial_path.name}", severity="error")
            return

        try:
            # Load JSON content
            content = self.trial_path.read_text()
            json_viewer.load_text(content)
            json_viewer.scroll_home(animate=False)

            # Configure and load TrialViewer
            # Path and renderer are already set during __init__ and passed to yield
            # We just need to trigger its loading mechanism if it doesn't load automatically on mount
            # (TrialViewer's on_mount should call load_and_display)
            # If TrialViewer needs an explicit call after mount:
            trial_viewer.load_and_display()
            log.info(f"Loaded trial data for {self.trial_path.name} into split view.")

        except Exception as e:
            log.error(f"Error loading trial file {self.trial_path}: {e}")
            error_msg = f"Error loading trial file:\n\n{e}"
            json_viewer.load_text(error_msg)
            self.app.notify(f"Error loading trial: {e}", severity="error")
            # Optionally show error in TrialViewer side too

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
            self.renderer = new_renderer_class
            trial_viewer = self.query_one("#trial-viewer-widget", TrialViewer)
            trial_viewer.renderer = new_renderer_class
            # Trigger a refresh of the TrialViewer's display
            trial_viewer.refresh_display()
            self.app.notify(f"Renderer set to: {renderer_name.capitalize()}")
        else:
            log.warning(f"Unknown renderer name: {renderer_name}")
            self.app.notify(f"Unknown renderer: {renderer_name}", severity="warning")
