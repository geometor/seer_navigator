import os
from pathlib import Path
from datetime import timedelta # Import timedelta
import re # Import re for sorting

from rich.text import Text

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, ListView, ListItem, DataTable, Header, Footer
from textual.reactive import reactive
from textual import log
from textual.containers import (
    Horizontal,
    Vertical,
    Grid,
    ScrollableContainer,
)
from textual.binding import Binding
from textual.widgets._data_table import ColumnKey
import json

# Import Task to calculate weight
from geometor.seer.tasks.tasks import Task
from geometor.seer_navigator.screens.task_screen import TaskScreen
from geometor.seer.session.level import Level  # Import Level


class TaskSessionsScreen(Screen):
    """Displays instances of a specific task across multiple sessions."""

    CSS = """
    Screen > Vertical {
        grid-size: 2;
        grid-rows: auto 1fr; /* Summary auto height, table takes rest */
    }
    #summary-grid {
        grid-size: 3; /* Three columns for the summary tables */
        grid-gutter: 1 2;
        height: auto; /* Let the grid determine its height */
        padding: 0 1; /* Add some horizontal padding */
        margin-bottom: 1; /* Space below summary */
    }
    .summary-table {
        height: auto; /* Fit content height */
        border: none; /* No border for summary tables */
    }
    /* Ensure no focus border on summary tables */
    .summary-table:focus {
        border: none;
    }
    DataTable { /* Style for the main tasks table */
        height: 1fr;
    }
    Vertical {height: 100%;}
    """
    BINDINGS = [
        Binding("l,enter", "select_row", "Select", show=False),
        Binding("k", "move_up", "Cursor up", show=False),
        Binding("j", "move_down", "Cursor down", show=False),
        Binding("h", "app.pop_screen", "back", show=False),
        Binding("i", "view_images", "View Images", show=True), # ADDED image view binding
        # Binding("[", "previous_sibling", "Previous Sibling", show=True), # Not applicable here
        # Binding("]", "next_sibling", "Next Sibling", show=True),     # Not applicable here
    ]

    def __init__(self, sessions_root: Path, task_id: str) -> None:
        super().__init__()
        self.sessions_root = sessions_root
        self.task_id = task_id
        self.task_instances: list[Path] = [] # List to store paths like sessions_root/session_name/task_id
        self.instance_index = 0
        self.current_sort_key: ColumnKey | None = None
        self.current_sort_reverse: bool = False

    def compose(self) -> ComposeResult:
        self.table = DataTable() # Main table showing task instances per session
        # Columns are the same as SessionScreen's task table, but first column is SESSION
        self.table.add_columns(
            "SESSION", # Changed from TASKS
            Text("ERROR", justify="center"),
            "TEST",
            "TRAIN",
            Text("SCORE", justify="right"),
            "STEPS",
            "TIME",
            Text("IN", justify="right"),
            Text("OUT", justify="right"),
            Text("TOTAL", justify="right"),
            Text("WEIGHT", justify="right"),
        )
        self.table.cursor_type = "row"

        yield Header()
        with Vertical():
            # Summary Grid with three DataTables
            with Grid(id="summary-grid"):
                yield DataTable(id="summary-table", show_header=False, cursor_type=None, classes="summary-table")
                yield DataTable(id="trials-table", show_header=False, cursor_type=None, classes="summary-table")
                yield DataTable(id="tokens-table", show_header=False, cursor_type=None, classes="summary-table")
            # Main tasks table
            yield self.table
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Task • {self.task_id}"
        self.sub_title = f"Across Sessions in {self.sessions_root.name}"
        self.table.cursor_type = "row"

        # Add columns to summary tables
        summary_table = self.query_one("#summary-table", DataTable)
        summary_table.add_columns("Metric", "Value", "Avg")
        trials_table = self.query_one("#trials-table", DataTable)
        trials_table.add_columns("Metric", "Value", "±")
        tokens_table = self.query_one("#tokens-table", DataTable)
        tokens_table.add_columns("Metric", "Value")

        self.table.focus()
        self.load_task_instances() # Load main table data
        self.update_summary() # Populate summary tables
        self.current_sort_key = None
        self.current_sort_reverse = False

    def load_task_instances(self):
        """Loads data for the specific task_id across all sessions."""
        self.table.clear()
        self.task_instances = [] # Clear previous instances

        task_weight = "-" # Calculate weight once (assuming it's the same task)
        task_json_path_found = None
        for session_dir in self.sessions_root.iterdir():
             if session_dir.is_dir():
                 task_instance_path = session_dir / self.task_id / "task.json"
                 if task_instance_path.exists():
                     task_json_path_found = task_instance_path
                     break # Found one, use it for weight calculation

        if task_json_path_found:
            try:
                with open(task_json_path_found, "r") as f_task:
                    task_data = json.load(f_task)
                task_obj = Task(self.task_id, task_data)
                task_weight = Text(str(task_obj.weight), justify="right")
            except (json.JSONDecodeError, Exception) as e_task:
                log.error(f"Error loading or processing {task_json_path_found} for weight: {e_task}")
                task_weight = Text("ERR", justify="right", style="bold red")
        else:
             log.warning(f"Could not find task.json for task {self.task_id} in any session to determine weight.")
             task_weight = Text("?", justify="right", style="dim")


        for session_dir in self.sessions_root.iterdir():
            if session_dir.is_dir():
                task_dir = session_dir / self.task_id
                if task_dir.is_dir():
                    summary_path = task_dir / "index.json"
                    session_name = session_dir.name # Get the session name

                    try:
                        # Load task summary from this specific session
                        with open(summary_path, "r") as f:
                            summary = json.load(f)

                        self.task_instances.append(task_dir) # Store the path to this task instance

                        num_steps = Text(str(summary.get("steps", 0)), justify="right")
                        time_str = (
                            Level._format_duration(summary.get("duration_seconds"))
                            if summary.get("duration_seconds") is not None
                            else "-"
                        )
                        # Check the 'has_errors' boolean field directly
                        has_errors = summary.get("has_errors", False) # Default to False if missing
                        error_text = (
                            Text("⚠", style="bold #FFD700", justify="center") # Use warning symbol
                            if has_errors
                            else Text("-", justify="center")
                        )
                        tokens_data = summary.get("tokens", {})
                        prompt_tokens = tokens_data.get("prompt_tokens")
                        candidates_tokens = tokens_data.get("candidates_tokens")
                        total_tokens = tokens_data.get("total_tokens")
                        in_tokens_text = Text(str(prompt_tokens) if prompt_tokens is not None else "-", justify="right")
                        out_tokens_text = Text(str(candidates_tokens) if candidates_tokens is not None else "-", justify="right")
                        total_tokens_text = Text(str(total_tokens) if total_tokens is not None else "-", justify="right")

                        if "train_passed" in summary and summary["train_passed"] is not None:
                            train_passed = (
                                Text("✔", style="green", justify="center")
                                if summary["train_passed"]
                                else Text("✘", style="red", justify="center")
                            )
                        else:
                            train_passed = Text("-", style="", justify="center")

                        if "test_passed" in summary and summary["test_passed"] is not None:
                            test_passed = (
                                Text("✔", style="green", justify="center")
                                if summary["test_passed"]
                                else Text("✘", style="red", justify="center")
                            )
                        else:
                            test_passed = Text("-", style="", justify="center")

                        best_score_text = (
                            f"{summary.get('best_score'):.2f}"
                            if summary.get("best_score") is not None
                            else "-"
                        )
                        best_score_text = Text(best_score_text, justify="right")

                        # Add the row, using session_name as the first column
                        self.table.add_row(
                            session_name,        # SESSION
                            error_text,          # ERROR
                            test_passed,         # TEST
                            train_passed,        # TRAIN
                            best_score_text,     # SCORE
                            num_steps,           # STEPS
                            time_str,            # TIME
                            in_tokens_text,      # IN
                            out_tokens_text,     # OUT
                            total_tokens_text,   # TOTAL
                            task_weight          # WEIGHT (same for all rows)
                        )

                    except FileNotFoundError:
                        log.warning(f"Missing index.json for task {self.task_id} in session {session_name}")
                        # Optionally add a row indicating missing data
                        # self.table.add_row(session_name, "-", "-", "-", "-", "-", "-", "-", "-", "-", "-")
                    except json.JSONDecodeError:
                        log.error(f"Invalid JSON in index.json for task {self.task_id} in session {session_name}")
                        # Optionally add a row indicating error
                        # self.table.add_row(session_name, Text("ERR", style="bold red"), "-", "-", "-", "-", "-", "-", "-", "-", "-")
                    except Exception as e:
                        log.error(f"Error processing task instance {task_dir.name} in session {session_name}: {e}")
                        # Optionally add a row indicating error
                        # self.table.add_row(session_name, Text("ERR", style="bold red"), "-", "-", "-", "-", "-", "-", "-", "-", "-")


        if self.task_instances:
            self.select_instance_by_index(self.instance_index)
        else:
            self.table.add_row(f"Task '{self.task_id}' not found in any session.")

    def update_summary(self):
        """Updates the summary tables for the specific task across displayed sessions."""
        summary_table = self.query_one("#summary-table", DataTable)
        trials_table = self.query_one("#trials-table", DataTable)
        tokens_table = self.query_one("#tokens-table", DataTable)

        num_instances = len(self.task_instances)
        total_steps_count = 0
        train_passed_count = 0
        test_passed_count = 0
        error_count = 0
        total_duration_seconds = 0.0
        best_scores = []
        total_prompt_tokens = 0
        total_candidates_tokens = 0
        total_tokens_all_instances = 0
        total_weight = 0 # Will be weight * num_instances if weight is valid

        task_weight_value = 0
        # Recalculate weight value for summary (could optimize by storing from load)
        task_json_path_found = None
        for session_dir in self.sessions_root.iterdir():
             if session_dir.is_dir():
                 task_instance_path = session_dir / self.task_id / "task.json"
                 if task_instance_path.exists():
                     task_json_path_found = task_instance_path
                     break
        if task_json_path_found:
            try:
                with open(task_json_path_found, "r") as f_task:
                    task_data = json.load(f_task)
                task_obj = Task(self.task_id, task_data)
                task_weight_value = task_obj.weight
            except: pass # Error already logged

        for task_instance_path in self.task_instances:
            summary_path = task_instance_path / "index.json"
            try:
                with open(summary_path, "r") as f:
                    task_summary = json.load(f)

                total_steps_count += task_summary.get("steps", 0)
                if task_summary.get("train_passed"):
                    train_passed_count += 1
                if task_summary.get("test_passed"):
                    test_passed_count += 1
                # Check the 'has_errors' boolean field directly for summary count
                if task_summary.get("has_errors", False):
                    error_count += 1

                duration = task_summary.get("duration_seconds")
                if duration is not None:
                    total_duration_seconds += duration

                score = task_summary.get("best_score")
                if score is not None:
                    best_scores.append(score)

                tokens_data = task_summary.get("tokens", {})
                prompt_tokens = tokens_data.get("prompt_tokens")
                candidates_tokens = tokens_data.get("candidates_tokens")
                total_tokens = tokens_data.get("total_tokens")

                if prompt_tokens is not None:
                    total_prompt_tokens += prompt_tokens
                if candidates_tokens is not None:
                    total_candidates_tokens += candidates_tokens
                if total_tokens is not None:
                    total_tokens_all_instances += total_tokens

            except (FileNotFoundError, json.JSONDecodeError):
                pass # Skip tasks with missing/invalid index.json

        if task_weight_value > 0:
            total_weight = task_weight_value * num_instances

        best_score_summary = (
            f"{min(best_scores):.2f}" if best_scores else "-"
        )
        formatted_total_duration = Level._format_duration(total_duration_seconds)
        test_percent = (test_passed_count / num_instances * 100) if num_instances > 0 else 0.0
        test_percent_str = f"{test_percent:.1f}%"
        diff = test_passed_count - train_passed_count
        diff_str = f"{diff:+}"
        avg_steps_per_instance = (total_steps_count / num_instances) if num_instances > 0 else 0.0
        avg_steps_str = f"{avg_steps_per_instance:.1f} avg"

        # Clear and update summary table
        summary_table.clear()
        summary_table.add_row(
            Text("steps:", justify="right"),
            Text(str(total_steps_count), justify="right"),
            Text(avg_steps_str, justify="right")
        )
        summary_table.add_row(
            Text("time:", justify="right"),
            Text(formatted_total_duration, justify="right"),
            Text("")
        )
        summary_table.add_row(
            Text("best:", justify="right"),
            Text(best_score_summary, justify="right"),
            Text("")
        )
        summary_table.add_row(
            Text("weight:", justify="right"),
            Text(f"{total_weight:,}" if total_weight > 0 else "-", justify="right"),
            Text("")
        )

        # Clear and update trials table
        trials_table.clear()
        trials_table.add_row(
            Text("sessions:", justify="right"),
            Text(str(num_instances), justify="right"),
            Text("")
        )
        trials_table.add_row(
            Text("test:", justify="right"),
            Text(str(test_passed_count), justify="right"),
            Text(test_percent_str, justify="right")
        )
        trials_table.add_row(
            Text("train:", justify="right"),
            Text(str(train_passed_count), justify="right"),
            Text(diff_str, justify="right")
        )
        trials_table.add_row(
            Text("errors:", justify="right"),
            Text(str(error_count), justify="right"),
            Text("")
        )

        # Clear and update tokens table
        tokens_table.clear()
        tokens_table.add_row(Text("in:", justify="right"), Text(f"{total_prompt_tokens:,}", justify="right"))
        tokens_table.add_row(Text("out:", justify="right"), Text(f"{total_candidates_tokens:,}", justify="right"))
        tokens_table.add_row(Text("total:", justify="right"), Text(f"{total_tokens_all_instances:,}", justify="right"))

    def select_instance_by_index(self, index: int) -> None:
        if 0 <= index < len(self.task_instances):
            self.instance_index = index
            self.table.move_cursor(row=index)

    def action_move_up(self):
        if not self.task_instances: return
        row = self.table.cursor_row - 1
        if row >= 0:
            self.table.move_cursor(row=row)
            self.instance_index = self.table.cursor_row

    def action_move_down(self):
        if not self.task_instances: return
        row = self.table.cursor_row + 1
        if row < len(self.task_instances):
            self.table.move_cursor(row=row)
            self.instance_index = self.table.cursor_row

    def action_select_row(self):
        if not self.task_instances: return
        row_id = self.table.cursor_row
        if row_id is None or not (0 <= row_id < len(self.task_instances)):
            return

        task_instance_path = self.task_instances[row_id] # Path like sessions_root/session_name/task_id
        session_path = task_instance_path.parent # Path like sessions_root/session_name
        task_path = task_instance_path # Keep the full path for TaskScreen

        # Get step directories for the selected task instance
        try:
            step_dirs = sorted([d for d in task_path.iterdir() if d.is_dir()])
        except FileNotFoundError:
            log.error(f"Task directory not found when selecting row: {task_path}")
            self.notify(f"Error: Task directory not found.", severity="error")
            return

        self.app.push_screen(TaskScreen(session_path, task_path, step_dirs))

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.action_select_row()

    # --- START ADDED IMAGE VIEW ACTION ---
    def action_view_images(self) -> None:
        """Action to trigger viewing images for the current task across sessions."""
        # The context path is the root of all sessions
        # The task_id is specific to this screen instance
        log.info(f"Triggering image view for task '{self.task_id}' in context '{self.sessions_root}'")
        # We need to call the app's action, which will push the modal
        # The app's action needs to know which screen is calling to pass the correct context
        self.app.action_view_images()
    # --- END ADDED IMAGE VIEW ACTION ---

    def refresh_content(self) -> None:
        """Reloads task instance data and updates the screen."""
        log.info(f"Refreshing TaskSessionsScreen content for task {self.task_id}...")
        current_cursor_row = self.table.cursor_row

        self.load_task_instances()
        self.update_summary()

        if current_cursor_row is not None and 0 <= current_cursor_row < self.table.row_count:
            self.table.move_cursor(row=current_cursor_row, animate=False)
        elif self.table.row_count > 0:
            self.table.move_cursor(row=0, animate=False)

        self.table.focus()

    def perform_sort(self, sort_key: ColumnKey) -> None:
        """Sorts the DataTable by the given column key."""
        log.info(f"Performing sort on TaskSessionsScreen by key: {sort_key}")

        reverse = False
        if self.current_sort_key == sort_key:
            reverse = not self.current_sort_reverse
        else:
            reverse = False

        self.current_sort_key = sort_key
        self.current_sort_reverse = reverse

        def get_sort_key(row_data):
            try:
                col_index = list(self.table.columns.keys()).index(sort_key)
                cell_data = row_data[col_index]
            except (ValueError, IndexError):
                log.error(f"Could not find index for sort key '{sort_key}'")
                return float('-inf') # Return comparable value instead of None

            key_str = str(sort_key)

            if key_str == "SESSION":
                return cell_data # Simple string sort

            if key_str in ["ERROR", "TEST", "TRAIN"]:
                plain_text = cell_data.plain if hasattr(cell_data, 'plain') else str(cell_data)
                if plain_text == "✔": return 1
                if plain_text == "✘": return -1
                if plain_text == "⚠": return -2
                return 0

            if key_str in ["SCORE", "STEPS", "WEIGHT", "IN", "OUT", "TOTAL"]:
                plain_text = cell_data.plain if hasattr(cell_data, 'plain') else str(cell_data)
                plain_text = plain_text.replace(',', '')
                if key_str == "WEIGHT" and plain_text in ["ERR", "?"]: return float('-inf')
                if plain_text == "-": return float('-inf')
                try:
                    return float(plain_text)
                except ValueError:
                    return float('-inf')

            if key_str == "TIME":
                time_str = cell_data.plain if hasattr(cell_data, 'plain') else str(cell_data)
                if time_str == "-": return -1
                try:
                    parts = list(map(int, time_str.split(':')))
                    if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
                    else: return float('-inf')
                except ValueError:
                    return float('-inf')

            return cell_data.plain if hasattr(cell_data, 'plain') else str(cell_data)

        try:
            # Sort the underlying data list first
            self.task_instances.sort(key=lambda task_path: get_sort_key(self._get_row_data_for_path(task_path)), reverse=reverse)
            # Reload the table from the sorted list
            self.load_task_instances() # This clears and repopulates based on self.task_instances order
            self.notify(f"Sorted by {str(self.table.columns[sort_key].label)} {'(desc)' if reverse else '(asc)'}")
        except Exception as e:
            log.error(f"Error during DataTable sort: {e}")
            self.notify(f"Error sorting table: {e}", severity="error")

    def _get_row_data_for_path(self, task_path: Path) -> tuple:
        """Helper to get row data tuple for sorting comparison, mirroring table columns."""
        # This is inefficient as it re-reads the file, but needed for sorting the path list
        summary_path = task_path / "index.json"
        session_name = task_path.parent.name
        task_weight = "-" # Simplified for sorting helper - actual weight is complex

        try:
            with open(summary_path, "r") as f:
                summary = json.load(f)

            num_steps = Text(str(summary.get("steps", 0)))
            time_str = Text(Level._format_duration(summary.get("duration_seconds")) if summary.get("duration_seconds") is not None else "-")
            has_errors = summary.get("errors", {}).get("count", 0) > 0
            error_text = Text("⚠") if has_errors else Text("-")
            tokens_data = summary.get("tokens", {})
            in_tokens_text = Text(str(tokens_data.get("prompt_tokens")) if tokens_data.get("prompt_tokens") is not None else "-")
            out_tokens_text = Text(str(tokens_data.get("candidates_tokens")) if tokens_data.get("candidates_tokens") is not None else "-")
            total_tokens_text = Text(str(tokens_data.get("total_tokens")) if tokens_data.get("total_tokens") is not None else "-")
            train_passed = Text("✔") if summary.get("train_passed") else (Text("✘") if summary.get("train_passed") is False else Text("-"))
            test_passed = Text("✔") if summary.get("test_passed") else (Text("✘") if summary.get("test_passed") is False else Text("-"))
            best_score_text = Text(f"{summary.get('best_score'):.2f}" if summary.get("best_score") is not None else "-")

            # Return tuple matching column order for get_sort_key
            return (
                session_name, error_text, test_passed, train_passed, best_score_text,
                num_steps, time_str, in_tokens_text, out_tokens_text, total_tokens_text,
                task_weight # Placeholder weight
            )
        except Exception:
             # Return a default tuple that sorts predictably on error
             return (session_name, Text("ERR"), Text("-"), Text("-"), Text("-"),
                     Text("-"), Text("-"), Text("-"), Text("-"), Text("-"),
                     Text("-"))
