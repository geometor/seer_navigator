from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.containers import Container # Import Container
from pathlib import Path
import argparse
import json
import re
import subprocess # ADDED import
import shutil # ADDED import
from textual import log # Added log
from textual.binding import Binding # Added Binding

# Import screens
from geometor.seer_navigator.screens.sessions_screen import SessionsScreen
from geometor.seer_navigator.screens.session_screen import SessionScreen
from geometor.seer_navigator.screens.task_screen import TaskScreen
from geometor.seer_navigator.screens.step_screen import StepScreen
# Import TrialViewer instead of TrialScreen
from geometor.seer_navigator.screens.trial_screen import TrialViewer
# Import the modal screens
from geometor.seer_navigator.screens.image_view_modal import ImageViewModal
from geometor.seer_navigator.screens.sort_modal import SortModal
from textual.widgets._data_table import ColumnKey # Ensure ColumnKey is imported
from textual.screen import Screen # Import Screen for type hinting

# Define DummyGrid first so it's always available
class DummyGrid(Static):
    """Placeholder widget used when real renderers fail to import."""
    def __init__(self, grid_data: list, *args, **kwargs):
        super().__init__("Renderer Import Error", *args, **kwargs)
        log.error("DummyGrid used - real renderer import failed.")

# Import renderers (adjust path if needed)
try:
    from geometor.seer_navigator.renderers import (
        SolidGrid,
        BlockGrid,
        CharGrid,
        TinyGrid,
    )
    RENDERERS = {
        "solid": SolidGrid,
        "block": BlockGrid,
        "char": CharGrid,
        "tiny": TinyGrid,
    }
except ImportError:
    log.error("Could not import grid renderers. Grid visualization will fail.")
    RENDERERS = {}
    # Assign the already defined DummyGrid in case of import failure
    SolidGrid = BlockGrid = CharGrid = TinyGrid = DummyGrid


class SessionsNavigator(App):

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        #  Binding("[", "previous_sibling", "Previous Sibling"),
        #  Binding("]", "next_sibling", "Next Sibling"),
        # Add renderer bindings (using Ctrl+ to avoid conflict with sort 's')
        Binding("ctrl+s", "set_renderer('solid')", "Solid", show=False),
        Binding("ctrl+c", "set_renderer('char')", "Char", show=False),
        Binding("ctrl+b", "set_renderer('block')", "Block", show=False),
        Binding("ctrl+t", "set_renderer('tiny')", "Tiny", show=False),
        Binding("r", "refresh_screen", "Refresh", show=True),
        Binding("i", "view_images", "View Images", show=True), # ADDED image view binding
        Binding("s", "sort_table", "Sort Table", show=True),   # ADDED sort binding (plain 's')
    ]

    def __init__(self, sessions_root: str = "./sessions"):
        super().__init__()
        self.sessions_root = Path(sessions_root)
        # Initialize renderer state - DummyGrid is now guaranteed to be defined
        self.renderer = RENDERERS.get("tiny", DummyGrid) # Default to TinyGrid or Dummy
        log.info(f"Initial renderer set to: {self.renderer.__name__}") # Log the actual default
        self._sxiv_checked = False # ADDED sxiv check state
        self._sxiv_path = None     # ADDED sxiv path cache


    def compose(self) -> ComposeResult:
        """Yield the initial container for the app's default screen."""
        # Yield an empty container to satisfy compose requirement.
        # The actual content is managed by pushing screens in on_mount.
        yield Container()

    def on_mount(self) -> None:
        # Push the initial screen
        self.push_screen(SessionsScreen(self.sessions_root))

    # --- START ADDED SXIV CHECK ---
    def _check_sxiv(self) -> str | None:
        """Check if sxiv exists and cache the path."""
        if not self._sxiv_checked:
            self._sxiv_path = shutil.which("sxiv")
            self._sxiv_checked = True
            if not self._sxiv_path:
                log.warning("'sxiv' command not found in PATH. Cannot open images externally.")
                self.notify("sxiv not found. Cannot open images.", severity="warning", timeout=5)
        return self._sxiv_path
    # --- END ADDED SXIV CHECK ---

    def action_previous_sibling(self) -> None:
        """Navigate to the previous sibling directory."""
        current_screen = self.screen
        if hasattr(current_screen, "previous_sibling"):
            current_screen.previous_sibling()


    def action_next_sibling(self) -> None:
        """Navigate to the next sibling directory."""
        current_screen = self.screen
        if hasattr(current_screen, "next_sibling"):
            current_screen.next_sibling()

    # Action to switch renderer
    def action_set_renderer(self, renderer_name: str) -> None:
        """Sets the grid renderer and refreshes the TrialScreen if active."""
        new_renderer = RENDERERS.get(renderer_name)
        if new_renderer and new_renderer != self.renderer:
            self.renderer = new_renderer
            log.info(f"Renderer changed to: {renderer_name}")
            self.notify(f"Renderer: {renderer_name.capitalize()}")

            # If the current screen is StepScreen, find the TrialViewer and refresh it
            if isinstance(self.screen, StepScreen):
                try:
                    # Find the TrialViewer widget within the StepScreen
                    trial_viewer = self.screen.query_one(TrialViewer)
                    # Update its renderer attribute
                    trial_viewer.renderer = new_renderer
                    # Refresh its display if it's the currently active view in the switcher
                    if self.screen.query_one("ContentSwitcher").current == "trial-viewer":
                        trial_viewer.refresh_display()
                except Exception as e:
                    # Catch potential errors if TrialViewer isn't found or refresh fails
                    log.error(f"Error refreshing TrialViewer in StepScreen: {e}")

        elif not new_renderer:
            log.warning(f"Unknown renderer name: {renderer_name}")

    def action_refresh_screen(self) -> None:
        """Calls the refresh method on the current screen if it exists."""
        current_screen = self.screen
        if hasattr(current_screen, "refresh_content"):
            log.info(f"Refreshing screen: {current_screen.__class__.__name__}")
            current_screen.refresh_content()
            self.notify("Screen refreshed")
        else:
            log.warning(f"Screen {current_screen.__class__.__name__} has no refresh_content method.")
            self.notify("Refresh not supported on this screen", severity="warning")

    # --- START ADDED IMAGE VIEWING ACTIONS ---
    def action_view_images(self) -> None:
        """Pushes the image view modal screen."""
        current_screen = self.screen
        context_path = None

        # Determine context path based on the current screen
        if isinstance(current_screen, SessionsScreen):
            context_path = current_screen.sessions_root
        elif isinstance(current_screen, SessionScreen):
            context_path = current_screen.session_path
        elif isinstance(current_screen, TaskScreen):
            context_path = current_screen.task_path
        elif isinstance(current_screen, StepScreen):
            context_path = current_screen.step_path
        else:
            log.warning(f"Image viewing not supported on screen: {current_screen.__class__.__name__}")
            self.notify("Image viewing not supported here.", severity="warning")
            return

        if context_path:
            log.info(f"Pushing ImageViewModal with context: {context_path}")
            self.push_screen(ImageViewModal(context_path=context_path))
        else:
            log.error("Could not determine context path for image viewing.")
            self.notify("Error determining context for image viewing.", severity="error")

    # Added task_id parameter to match the call signature from ImageViewModal
    def launch_sxiv(self, context_path: Path, filter_type: str, task_id: str | None = None) -> None:
        """Finds images based on filter and launches sxiv. task_id is ignored in this navigator."""
        # Log the received task_id, even if unused, for debugging
        log.info(f"launch_sxiv called in SessionsNavigator with context={context_path}, filter={filter_type}, task_id={task_id}")
        sxiv_cmd = self._check_sxiv()
        if not sxiv_cmd:
            return # sxiv not found, notification already shown

        all_found_files = [] # Store all initially found files
        unique_task_images = {} # Dict to store {task_id: first_image_path}
        final_image_files = [] # List to pass to sxiv

        try:
            log.info(f"Searching for images in {context_path} with filter: {filter_type}")

            # --- Step 1: Find all potentially relevant files ---
            if filter_type == "all":
                all_found_files = sorted(list(context_path.rglob("*.png")))
                final_image_files = all_found_files # No uniqueness needed for 'all'
            elif filter_type == "tasks":
                all_found_files = sorted(list(context_path.rglob("**/task.png"))) # Use **/ to ensure we get task dir
            elif filter_type == "trials":
                all_found_files = sorted(list(context_path.rglob("*trial.png")))
                final_image_files = all_found_files # No uniqueness needed for 'trials'
            elif filter_type == "passed_trials":
                passed_trial_files = []
                json_files = list(context_path.rglob("*trial.json"))
                log.info(f"Found {len(json_files)} *trial.json files for passed_trials filter.")
                for json_file in json_files:
                    try:
                        with open(json_file, "r") as f:
                            trial_data = json.load(f)
                        # Check if 'test' trials exist and any have "match": true
                        test_trials = (trial_data.get("test") or {}).get("trials", [])
                        if any(trial.get("match") is True for trial in test_trials):
                            # Construct the expected PNG filename
                            png_filename = json_file.stem + ".png" # e.g., "code_00_trial.json" -> "code_00_trial.png"
                            png_path = json_file.with_name(png_filename)
                            if png_path.exists():
                                passed_trial_files.append(png_path) # Use the correct list name
                                log.debug(f"Adding passed trial image: {png_path}")
                            else:
                                log.warning(f"Passed trial JSON found ({json_file}), but corresponding PNG not found: {png_path}")
                    except json.JSONDecodeError:
                        log.error(f"Could not decode JSON for passed_trials filter: {json_file}")
                    except Exception as e:
                        log.error(f"Error processing {json_file} for passed_trials filter: {e}")
                all_found_files = sorted(passed_trial_files) # Store all passed trial images
            else:
                log.warning(f"Unknown image filter type: {filter_type}")
                self.notify(f"Unknown image filter: {filter_type}", severity="warning")
                return

            # --- Step 2: Apply uniqueness filter if needed ---
            if filter_type in ["tasks", "passed_trials"]:
                for img_path in all_found_files:
                    try:
                        # Assuming structure .../session_id/task_id/...
                        task_id_dir = img_path.parent # For task.png, parent is task_id dir
                        if filter_type == "passed_trials":
                            # For *trial.png, parent is step dir, grandparent is task_id dir
                            task_id_dir = img_path.parent.parent
                        task_id_str = task_id_dir.name
                        if task_id_str not in unique_task_images:
                            unique_task_images[task_id_str] = img_path
                            log.debug(f"Adding unique image for task '{task_id_str}': {img_path}")
                    except IndexError:
                        log.warning(f"Could not determine task ID for image path: {img_path}")
                    except Exception as e:
                        log.error(f"Error extracting task ID for uniqueness filter on {img_path}: {e}")

                final_image_files = sorted(list(unique_task_images.values())) # Get unique paths and sort them
                log.info(f"Applied uniqueness filter: {len(all_found_files)} found -> {len(final_image_files)} unique.")
            # else: final_image_files is already set for 'all' and 'trials'

            if not final_image_files:
                self.notify(f"No images found for filter '{filter_type}' in {context_path.name}.", severity="information")
                log.info(f"No images found for filter '{filter_type}' in {context_path}")
                return

            # Prepare the command list
            command = [sxiv_cmd] + [str(img_path) for img_path in final_image_files]

            log.info(f"Opening {len(final_image_files)} images with sxiv (filter: {filter_type})")
            subprocess.Popen(command)

        except FileNotFoundError:
            # This case should be caught by _check_sxiv, but handle defensively
            log.error(f"'sxiv' command not found when trying to execute.")
            self.notify("sxiv not found. Cannot open images.", severity="error")
        except Exception as e:
            log.error(f"Error finding or opening images with sxiv from {context_path}: {e}")
            self.notify(f"Error viewing images: {e}", severity="error")
    # --- END ADDED IMAGE VIEWING ACTIONS ---

    # --- START ADDED SORT ACTION ---
    def action_sort_table(self) -> None:
        """Pushes the SortModal screen to select a column for sorting."""
        # Get the currently active screen
        current_screen = self.screen_stack[-1]

        # Check if the current screen has a sortable table
        if hasattr(current_screen, "table") and hasattr(current_screen.table, "columns") and current_screen.table.columns:
            log.info(f"Opening SortModal for screen: {current_screen.__class__.__name__}")

            # Define the callback function to handle the result from SortModal
            def handle_sort_dismiss(selected_key: ColumnKey | None) -> None:
                """Callback executed when SortModal is dismissed."""
                # Ensure the screen context is still valid (might have changed)
                active_screen = self.screen_stack[-1]
                if selected_key:
                    log.info(f"SortModal dismissed for {active_screen.__class__.__name__}, sorting by: {selected_key}")
                    if hasattr(active_screen, "perform_sort"):
                        try:
                            # Call perform_sort on the screen that was active
                            active_screen.perform_sort(selected_key)
                        except Exception as e:
                            log.exception(f"Error calling perform_sort on {active_screen.__class__.__name__} after SortModal dismiss: {e}")
                            self.notify(f"Error during sort: {e}", severity="error")
                    else:
                        log.error(f"Screen {active_screen.__class__.__name__} has no perform_sort method.")
                        self.notify("Sort function not implemented on current screen.", severity="error")
                else:
                    log.info(f"SortModal dismissed (cancelled) for {active_screen.__class__.__name__}.")

            # Push the SortModal screen with the callback
            self.push_screen(
                SortModal(columns=current_screen.table.columns),
                handle_sort_dismiss # Pass the callback function
            )
        else:
            log.warning("Attempted to sort on a screen without a valid table/columns.")
            self.notify("No sortable table on the current screen.", severity="warning")
    # --- END ADDED SORT ACTION ---

    def action_quit(self) -> None:
        """Quits the application"""
        self.exit()

def run():
    parser = argparse.ArgumentParser(description="Navigate ARC test sessions.")
    parser.add_argument(
        "--sessions-dir",
        type=str,
        default=".",
        help="Path to the sessions directory",
    )
    args = parser.parse_args()

    app = SessionsNavigator(sessions_root=args.sessions_dir)
    app.run()


if __name__ == "__main__":
    run()
