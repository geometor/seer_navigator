import argparse
from pathlib import Path
import subprocess # ADDED import
import shutil # ADDED import
import json # ADDED import

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.binding import Binding
from textual import log

# Import screens
from geometor.seer_navigator.screens.tasks_screen import TasksScreen
from geometor.seer_navigator.screens.sort_modal import SortModal # ADDED
from geometor.seer_navigator.screens.image_view_modal import ImageViewModal # ADDED


class TasksNavigator(App):
    """A Textual app to navigate aggregated task data across sessions."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_screen", "Refresh", show=True),
        Binding("s", "sort_table", "Sort Table", show=True),   # ADDED sort binding
        Binding("i", "view_images", "View Images", show=True), # ADDED image view binding
    ]

    def __init__(self, sessions_root: str = "./sessions"):
        super().__init__()
        self.sessions_root = Path(sessions_root)
        log.info(f"TasksNavigator initialized with sessions_root: {self.sessions_root}")
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

        # Determine context path based on the current screen
        # For TasksNavigator, the main context is always the sessions_root
        if isinstance(current_screen, TasksScreen):
            context_path = current_screen.sessions_root
        else:
            # This case shouldn't typically happen in TasksNavigator, but handle defensively
            log.warning(f"Image viewing not supported on screen: {current_screen.__class__.__name__}")
            self.notify("Image viewing not supported here.", severity="warning")
            return

        if context_path:
            log.info(f"Pushing ImageViewModal with context: {context_path}")
            self.push_screen(ImageViewModal(context_path=context_path))
        else:
            # Should not happen if current_screen is TasksScreen, but check anyway
            log.error("Could not determine context path for image viewing.")
            self.notify("Error determining context for image viewing.", severity="error")

    def launch_sxiv(self, context_path: Path, filter_type: str) -> None:
        """Finds images based on filter and launches sxiv."""
        sxiv_cmd = self._check_sxiv()
        if not sxiv_cmd:
            return # sxiv not found, notification already shown

        image_files = []
        try:
            log.info(f"Searching for images in {context_path} with filter: {filter_type}")
            if filter_type == "all":
                image_files = sorted(list(context_path.rglob("*.png")))
            elif filter_type == "tasks":
                # Find task.png files recursively
                image_files = sorted(list(context_path.rglob("task.png")))
            elif filter_type == "trials":
                # Find *trial.png files recursively
                image_files = sorted(list(context_path.rglob("*trial.png")))
            elif filter_type == "passed_trials":
                # Find *trial.png files where the corresponding .json shows test success
                # In TasksNavigator context, this means checking across all sessions
                image_files = []
                all_trial_jsons = list(context_path.rglob("*trial.json")) # Find all trial json files first
                log.info(f"Found {len(all_trial_jsons)} *trial.json files for passed_trials filter.")
                for json_file in all_trial_jsons:
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
                                image_files.append(png_path)
                                log.debug(f"Adding passed trial image: {png_path}")
                            else:
                                log.warning(f"Passed trial JSON found ({json_file}), but corresponding PNG not found: {png_path}")
                    except json.JSONDecodeError:
                        log.error(f"Could not decode JSON for passed_trials filter: {json_file}")
                    except Exception as e:
                        log.error(f"Error processing {json_file} for passed_trials filter: {e}")
                image_files = sorted(list(set(image_files))) # Use set to remove duplicates across sessions, then sort
            else:
                log.warning(f"Unknown image filter type: {filter_type}")
                self.notify(f"Unknown image filter: {filter_type}", severity="warning")
                return

            if not image_files:
                self.notify(f"No images found for filter '{filter_type}' in {context_path.name}.", severity="information")
                log.info(f"No images found for filter '{filter_type}' in {context_path}")
                return

            # Prepare the command list
            command = [sxiv_cmd] + [str(img_path) for img_path in image_files]

            log.info(f"Opening {len(image_files)} images with sxiv (filter: {filter_type})")
            subprocess.Popen(command)

        except FileNotFoundError:
            # This case should be caught by _check_sxiv, but handle defensively
            log.error(f"'sxiv' command not found when trying to execute.")
            self.notify("sxiv not found. Cannot open images.", severity="error")
        except Exception as e:
            log.error(f"Error finding or opening images with sxiv from {context_path}: {e}")
            self.notify(f"Error viewing images: {e}", severity="error")
    # --- END ADDED IMAGE VIEWING ACTIONS ---


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
