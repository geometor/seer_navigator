import argparse
from pathlib import Path
import subprocess # ADDED import
import shutil # ADDED import
import json # ADDED import

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.binding import Binding
from textual import log
from textual.widgets import Static # ADDED Static for DummyGrid

# --- START ADDED RENDERER IMPORTS ---
# Define DummyGrid first so it's always available
class DummyGrid(Static):
    """Placeholder widget used when real renderers fail to import."""
    def __init__(self, grid_data: list, *args, **kwargs):
        super().__init__("Renderer Import Error", *args, **kwargs)
        log.error("DummyGrid used - real renderer import failed.")

try:
    from geometor.seer_navigator.renderers import (
        SolidGrid,
        CharGrid,
        BlockGrid,
        TinyGrid,
        # ImageGrid, # Not typically used directly here
    )
    DEFAULT_RENDERER = TinyGrid # Changed default to TinyGrid
except ImportError:
    log.error("Could not import grid renderers. Grid visualization will fail.")
    # Assign the already defined DummyGrid in case of import failure
    SolidGrid = CharGrid = BlockGrid = TinyGrid = DummyGrid # Assign DummyGrid to all renderer types
    DEFAULT_RENDERER = DummyGrid
# --- END ADDED RENDERER IMPORTS ---

# Import screens
from geometor.seer_navigator.screens.tasks_screen import TasksScreen
from geometor.seer_navigator.screens.task_sessions_screen import TaskSessionsScreen # ADDED
from geometor.seer_navigator.screens.sort_modal import SortModal # ADDED
from geometor.seer_navigator.screens.image_view_modal import ImageViewModal # ADDED


class TasksNavigator(App):
    """A Textual app to navigate aggregated task data across sessions."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_screen", "Refresh", show=True),
        Binding("s", "sort_table", "Sort Table", show=True),
        Binding("i", "view_images", "View Images", show=True),
        # --- START ADDED RENDERER BINDINGS ---
        Binding("ctrl+s", "set_renderer('solid')", "Solid", show=False), # Use Ctrl+ to avoid conflict with sort
        Binding("ctrl+c", "set_renderer('char')", "Char", show=False),
        Binding("ctrl+b", "set_renderer('block')", "Block", show=False),
        Binding("ctrl+t", "set_renderer('tiny')", "Tiny", show=False),
        # --- END ADDED RENDERER BINDINGS ---
    ]

    def __init__(self, sessions_root: str = "./sessions"):
        super().__init__()
        self.sessions_root = Path(sessions_root)
        self.renderer: type[Static] = DEFAULT_RENDERER # Use the updated DEFAULT_RENDERER
        log.info(f"TasksNavigator initialized with sessions_root: {self.sessions_root}, default renderer: {self.renderer.__name__}")
        self._sxiv_checked = False # ADDED sxiv check state
        self._sxiv_path = None     # ADDED sxiv path cache

    def compose(self) -> ComposeResult:
        """Yield the initial container for the app's default screen."""
        yield Container() # Container to hold the pushed screen

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Push the initial screen
        self.push_screen(TasksScreen(self.sessions_root))

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

    # --- START ADDED SORT ACTION ---
    def action_sort_table(self) -> None:
        """Pushes the sort modal screen for the current data table."""
        current_screen = self.screen

        # Check if the current screen has a sortable table (TasksScreen)
        if isinstance(current_screen, TasksScreen) and hasattr(current_screen, "table") and hasattr(current_screen, "perform_sort"):
            table = current_screen.table
            columns = table.columns # Get the columns dictionary

            if not columns:
                self.notify("No columns available to sort.", severity="warning")
                return

            log.info(f"Pushing SortModal for screen: {current_screen.__class__.__name__}")
            # Pass the parent screen instance and the columns dict
            self.push_screen(SortModal(parent_screen=current_screen, columns=columns))
        else:
            log.warning(f"Sorting not supported on screen: {current_screen.__class__.__name__}")
            self.notify("Sorting not supported on this screen.", severity="warning")
    # --- END ADDED SORT ACTION ---

    # --- START ADDED IMAGE VIEWING ACTIONS ---
    def action_view_images(self) -> None:
        """Pushes the image view modal screen."""
        current_screen = self.screen
        context_path = None
        task_id = None # Initialize task_id

        # Determine context path and potentially task_id based on the current screen
        if isinstance(current_screen, TasksScreen):
            context_path = current_screen.sessions_root
            # task_id remains None for the main TasksScreen
        elif isinstance(current_screen, TaskSessionsScreen): # ADDED case for TaskSessionsScreen
            context_path = current_screen.sessions_root
            task_id = current_screen.task_id # Get the specific task_id
        else:
            log.warning(f"Image viewing not supported on screen: {current_screen.__class__.__name__}")
            self.notify("Image viewing not supported here.", severity="warning")
            return

        if context_path:
            log.info(f"Pushing ImageViewModal with context: {context_path}, task_id: {task_id}")
            # Pass task_id (which might be None) to the modal
            self.push_screen(ImageViewModal(context_path=context_path, task_id=task_id))
        else:
            log.error("Could not determine context path for image viewing.")
            self.notify("Error determining context for image viewing.", severity="error")

    def launch_sxiv(self, context_path: Path, filter_type: str, task_id: str | None = None) -> None: # Added task_id parameter
        """Finds images based on filter and launches sxiv. Filters by task_id if provided."""
        sxiv_cmd = self._check_sxiv()
        if not sxiv_cmd:
            return # sxiv not found, notification already shown

        all_found_files = [] # Store all initially found files
        unique_task_images = {} # Dict to store {task_id: first_image_path}
        final_image_files = [] # List to pass to sxiv

        try:
            log.info(f"Searching for images in {context_path} with filter: {filter_type}, task_id: {task_id}")

            # --- Step 1: Find all potentially relevant files based on task_id context ---
            if filter_type == "all":
                pattern = f"*/{task_id}/**/*.png" if task_id else "**/*.png"
                all_found_files = sorted(list(context_path.rglob(pattern)))
                final_image_files = all_found_files # No uniqueness needed for 'all'
            elif filter_type == "tasks":
                pattern = f"*/{task_id}/task.png" if task_id else "**/task.png"
                all_found_files = sorted(list(context_path.rglob(pattern)))
            elif filter_type == "trials":
                pattern = f"*/{task_id}/*trial.png" if task_id else "**/*trial.png"
                all_found_files = sorted(list(context_path.rglob(pattern)))
                final_image_files = all_found_files # No uniqueness needed for 'trials'
            elif filter_type == "passed_trials":
                passed_trial_files = []
                json_pattern = f"*/{task_id}/*trial.json" if task_id else "**/*trial.json"
                relevant_trial_jsons = list(context_path.rglob(json_pattern))
                log.info(f"Found {len(relevant_trial_jsons)} *trial.json files for passed_trials filter (task_id: {task_id}).")

                for json_file in relevant_trial_jsons:
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

            # --- Step 2: Apply uniqueness filter if needed (only when task_id is NOT specified) ---
            # If task_id *is* specified, the rglob already limited results to that task,
            # so uniqueness isn't strictly needed, but we apply it for consistency.
            if filter_type in ["tasks", "passed_trials"]:
                for img_path in all_found_files:
                    try:
                        # Assuming structure .../session_id/task_id/...
                        task_id_dir = img_path.parent # For task.png
                        if filter_type == "passed_trials":
                            task_id_dir = img_path.parent.parent # For *trial.png

                        task_id_str = task_id_dir.name
                        if task_id_str not in unique_task_images:
                            unique_task_images[task_id_str] = img_path
                            log.debug(f"Adding unique image for task '{task_id_str}': {img_path}")
                    except IndexError:
                         log.warning(f"Could not determine task ID for image path: {img_path}")
                    except Exception as e:
                         log.error(f"Error extracting task ID for uniqueness filter on {img_path}: {e}")

                final_image_files = sorted(list(unique_task_images.values()))
                log.info(f"Applied uniqueness filter: {len(all_found_files)} found -> {len(final_image_files)} unique.")
            # else: final_image_files is already set for 'all' and 'trials'

            if not final_image_files:
                self.notify(f"No images found for filter '{filter_type}' in {context_path.name}.", severity="information")
                log.info(f"No images found for filter '{filter_type}' in {context_path}")
                return

            # Prepare the command list
            command = [sxiv_cmd] + [str(img_path) for img_path in final_image_files]

            log.info(f"Opening {len(final_image_files)} images with sxiv (filter: {filter_type}, task_id: {task_id})")
            subprocess.Popen(command)

        except FileNotFoundError:
            # This case should be caught by _check_sxiv, but handle defensively
            log.error(f"'sxiv' command not found when trying to execute.")
            self.notify("sxiv not found. Cannot open images.", severity="error")
        except Exception as e:
            log.error(f"Error finding or opening images with sxiv from {context_path}: {e}")
            self.notify(f"Error viewing images: {e}", severity="error")
    # --- END ADDED IMAGE VIEWING ACTIONS ---

    # --- START ADDED RENDERER ACTION ---
    def action_set_renderer(self, renderer_name: str) -> None:
        """Sets the active grid renderer."""
        renderer_map = {
            "solid": SolidGrid,
            "char": CharGrid,
            "block": BlockGrid,
            "tiny": TinyGrid,
            # "image": ImageGrid, # If needed later
        }
        new_renderer = renderer_map.get(renderer_name)

        if new_renderer and new_renderer != self.renderer:
            # Check if the selected renderer is available (didn't fail import)
            if new_renderer == DummyGrid:
                 log.warning(f"Attempted to set unavailable renderer: {renderer_name}")
                 self.notify(f"Renderer '{renderer_name}' failed to import.", severity="warning")
                 return

            self.renderer = new_renderer
            log.info(f"Switched renderer to: {renderer_name}")
            self.notify(f"Renderer set to: {renderer_name.capitalize()}")

            # Refresh the current screen if it displays trials that use the renderer
            # StepScreen handles this via watch_selected_file_path, but a general refresh might be needed
            # if other screens start using the renderer directly.
            current_screen = self.screen
            if hasattr(current_screen, "refresh_content"):
                 # Check if the screen has a TrialViewer that needs updating
                 try:
                     trial_viewer = current_screen.query_one("TrialViewer") # Assumes TrialViewer has default ID
                     if trial_viewer:
                         log.info(f"Refreshing screen {current_screen.__class__.__name__} due to renderer change.")
                         current_screen.refresh_content() # Trigger refresh which should update TrialViewer
                 except Exception:
                     pass # No TrialViewer found or other query error, ignore.

        elif not new_renderer:
            log.warning(f"Unknown renderer name: {renderer_name}")
            self.notify(f"Unknown renderer: {renderer_name}", severity="warning")
    # --- END ADDED RENDERER ACTION ---

    def action_quit(self) -> None:
        """Quits the application"""
        self.exit()


def run():
    parser = argparse.ArgumentParser(description="Navigate aggregated ARC task data across sessions.")
    parser.add_argument(
        "--sessions-dir",
        type=str,
        default=".",
        help="Path to the root sessions directory",
    )
    args = parser.parse_args()

    app = TasksNavigator(sessions_root=args.sessions_dir)
    app.run()



if __name__ == "__main__":
    run()
