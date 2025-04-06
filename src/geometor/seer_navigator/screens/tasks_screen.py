import json
from pathlib import Path
from collections import defaultdict

from rich.text import Text

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Header, Footer, Static # Added Static
from textual.reactive import reactive # ADDED reactive
from textual.containers import Vertical
from textual.binding import Binding
from textual.widgets._data_table import ColumnKey # ADDED ColumnKey
from textual import log


# Import Grid
from textual.containers import Vertical, Grid

# Import Task for weight calculation
from geometor.seer.tasks.tasks import Task

# Import the new screen
from .task_sessions_screen import TaskSessionsScreen # ADDED


class TasksScreen(Screen):
    """Displays aggregated task data across all sessions."""

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
    #tasks-table { /* Style for the main tasks table */
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Cursor Down", show=False),
        Binding("k", "cursor_up", "Cursor Up", show=False),
        Binding("l,enter", "select_task", "Select Task", show=True), # ENABLED task selection
        # Binding("h", "app.pop_screen", "Back", show=False), # REMOVED - TasksScreen is root
    ]

    def __init__(self, sessions_root: Path) -> None:
        super().__init__()
        self.sessions_root = sessions_root
        self.tasks_summary = defaultdict(lambda: {
            'sessions': set(),
            'errors': 0,
            'test_passed': 0,
            'train_passed': 0,
            'total_steps': 0, # Add total steps
            'total_duration': 0.0, # Add total duration
            'best_score': float('inf'), # Initialize best score to infinity (lower is better)
            # ADDED token aggregation fields
            'total_prompt_tokens': 0,
            'total_candidates_tokens': 0,
            'total_tokens': 0,
            'weight': 0, # ADDED weight field
        })
        self.sorted_task_ids = [] # To maintain table order
        self.current_sort_key: ColumnKey | None = None # ADDED sort state
        self.current_sort_reverse: bool = False      # ADDED sort state

    def compose(self) -> ComposeResult:
        self.table = DataTable(id="tasks-table") # Main tasks table

        yield Header()
        with Vertical():
            # Summary Grid with three DataTables
            with Grid(id="summary-grid"):
                yield DataTable(id="summary-table", show_header=False, cursor_type=None, classes="summary-table")
                yield DataTable(id="trials-table", show_header=False, cursor_type=None, classes="summary-table")
                yield DataTable(id="tokens-table", show_header=False, cursor_type=None, classes="summary-table") # Placeholder for now
            # Main tasks table
            yield self.table
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.title = "SEER Tasks"
        self.sub_title = f"{self.sessions_root.parent.name}"

        # Add columns to summary tables
        summary_table = self.query_one("#summary-table", DataTable)
        summary_table.add_columns("Metric", "Value")
        trials_table = self.query_one("#trials-table", DataTable)
        trials_table.add_columns("Metric", "Value", "±") # Add third column header
        tokens_table = self.query_one("#tokens-table", DataTable)
        tokens_table.add_columns("Metric", "Value")

        # Setup main table
        self.table.cursor_type = "row"
        # Add columns: TASK, SESSIONS, ERRORS, TEST, TRAIN, STEPS, TIME, BEST
        self.table.add_columns(
            "TASK",
            Text("SESSIONS", justify="right"),
            Text("ERRORS", justify="center"),
            Text("TEST", justify="right"),
            Text("TRAIN", justify="right"),
            Text("STEPS", justify="right"),
            Text("TIME", justify="right"),
            Text("BEST", justify="right"),
            # ADDED Token Columns
            Text("IN", justify="right"),
            Text("OUT", justify="right"),
            Text("TOTAL", justify="right"),
            Text("WEIGHT", justify="right"), # ADDED WEIGHT column
        )

        self.load_and_display_tasks() # This will now also call update_summary
        self.table.focus()
        # Add sort key tracking
        self.current_sort_key = None
        self.current_sort_reverse = False

    def load_and_display_tasks(self):
        """Scans sessions, aggregates task data, and populates the DataTable."""
        log.info(f"Scanning sessions in {self.sessions_root} to aggregate task data...")
        self.tasks_summary.clear() # Clear previous data before rescanning

        try:
            if not self.sessions_root.is_dir():
                log.error(f"Sessions root directory not found: {self.sessions_root}")
                self.notify(f"Error: Directory not found: {self.sessions_root}", severity="error")
                return

            for session_dir in self.sessions_root.iterdir():
                if session_dir.is_dir():
                    session_name = session_dir.name
                    for task_dir in session_dir.iterdir():
                        if task_dir.is_dir():
                            task_id = task_dir.name
                            summary_path = task_dir / "index.json"
                            task_data = self.tasks_summary[task_id] # Get or create entry

                            task_data['sessions'].add(session_name)

                            if summary_path.exists():
                                try:
                                    with open(summary_path, "r") as f:
                                        summary = json.load(f)

                                    # Aggregate counts
                                    # Increment 'errors' if the task had errors in this session
                                    if summary.get("has_errors", False):
                                        task_data['errors'] += 1
                                    if summary.get("test_passed") is True:
                                        task_data['test_passed'] += 1
                                    if summary.get("train_passed") is True:
                                        task_data['train_passed'] += 1
                                    task_data['total_steps'] += summary.get("steps", 0)

                                    # Aggregate duration
                                    duration = summary.get("duration_seconds")
                                    if duration is not None:
                                        task_data['total_duration'] += duration

                                    # Find best (minimum) score
                                    score = summary.get("best_score")
                                    if score is not None and score < task_data['best_score']:
                                        task_data['best_score'] = score

                                    # --- START ADDED TOKEN AGGREGATION ---
                                    tokens_data = summary.get("tokens", {})
                                    prompt_tokens = tokens_data.get("prompt_tokens")
                                    candidates_tokens = tokens_data.get("candidates_tokens")
                                    total_tokens = tokens_data.get("total_tokens")

                                    if prompt_tokens is not None:
                                        task_data['total_prompt_tokens'] += prompt_tokens
                                    if candidates_tokens is not None:
                                        task_data['total_candidates_tokens'] += candidates_tokens
                                    if total_tokens is not None:
                                        task_data['total_tokens'] += total_tokens
                                    # --- END ADDED TOKEN AGGREGATION ---

                                    # --- START ADDED WEIGHT CALCULATION ---
                                    # Find the corresponding task.json in *any* session dir for this task
                                    task_json_path = None
                                    for s_dir in self.sessions_root.iterdir():
                                        potential_path = s_dir / task_id / "task.json"
                                        if potential_path.exists():
                                            task_json_path = potential_path
                                            break # Found one, no need to check others

                                    if task_json_path:
                                        try:
                                            with open(task_json_path, "r") as f_task:
                                                task_json_data = json.load(f_task)
                                            task_obj = Task(task_id, task_json_data)
                                            task_data['weight'] = task_obj.weight # Store weight
                                        except (json.JSONDecodeError, Exception) as e_task:
                                            log.error(f"Error loading/processing {task_json_path} for weight: {e_task}")
                                            task_data['weight'] = -1 # Indicate error
                                    else:
                                        log.warning(f"Could not find task.json for task {task_id} in any session.")
                                        task_data['weight'] = -2 # Indicate not found
                                    # --- END ADDED WEIGHT CALCULATION ---

                                except json.JSONDecodeError:
                                    log.warning(f"Could not decode JSON in {summary_path}")
                                    task_data['errors'] += 1 # Count decode error as an error
                                except Exception as e:
                                    log.error(f"Error reading {summary_path}: {e}")
                                    task_data['errors'] += 1 # Count other read errors
                            else:
                                # If index.json is missing, maybe log or count as error?
                                log.warning(f"Missing index.json for task {task_id} in session {session_name}")
                                # task_data['errors'] += 1 # Optionally count missing index as error

        except Exception as e:
            log.error(f"Error scanning directories: {e}")
            self.notify(f"Error scanning sessions: {e}", severity="error")
            # Display error in table?
            table = self.query_one(DataTable)
            table.clear()
            table.add_row(Text(f"Error scanning: {e}", style="bold red"))
            return

        # Populate the main DataTable
        self.table.clear()

        # Sort tasks by ID for consistent display order
        self.sorted_task_ids = sorted(self.tasks_summary.keys())

        if not self.sorted_task_ids:
            self.table.add_row("No tasks found.")
            self.update_summary() # Update summary even if no tasks
            return

        for task_id in self.sorted_task_ids:
            data = self.tasks_summary[task_id]
            session_count = len(data['sessions'])
            error_text = Text(str(data['errors']), style="bold #FFD700", justify="center") if data['errors'] > 0 else Text("-", justify="center")

            # Color TEST and TRAIN counts
            test_passed_count = data['test_passed']
            test_text = (
                Text(str(test_passed_count), style="bold green", justify="right")
                if test_passed_count > 0
                else Text("0", style="red", justify="right")
            )
            train_passed_count = data['train_passed']
            train_text = (
                Text(str(train_passed_count), style="bold green", justify="right")
                if train_passed_count > 0
                else Text("0", style="red", justify="right")
            )

            steps_text = Text(str(data['total_steps']), justify="right")
            # Format duration
            time_str = self._format_duration(data['total_duration'])
            # Format best score
            best_score_val = data['best_score']
            best_score_text = Text(f"{best_score_val:.2f}" if best_score_val != float('inf') else "-", justify="right")

            # --- START ADDED TOKEN TEXT ---
            in_tokens_text = Text(f"{data['total_prompt_tokens']:,}" if data['total_prompt_tokens'] > 0 else "-", justify="right")
            out_tokens_text = Text(f"{data['total_candidates_tokens']:,}" if data['total_candidates_tokens'] > 0 else "-", justify="right")
            total_tokens_text = Text(f"{data['total_tokens']:,}" if data['total_tokens'] > 0 else "-", justify="right")
            # --- END ADDED TOKEN TEXT ---

            # --- START ADDED WEIGHT TEXT ---
            weight_val = data.get('weight', 0)
            if weight_val == -1:
                weight_text = Text("ERR", style="bold red", justify="right")
            elif weight_val == -2:
                weight_text = Text("?", style="dim", justify="right")
            else:
                weight_text = Text(f"{weight_val:,}", justify="right")
            # --- END ADDED WEIGHT TEXT ---

            self.table.add_row(
                task_id,                       # TASK
                Text(str(session_count), justify="right"), # SESSIONS
                error_text,                    # ERRORS
                test_text,                     # TEST
                train_text,                    # TRAIN
                steps_text,                    # STEPS
                Text(time_str, justify="right"), # TIME
                best_score_text,               # BEST
                # ADDED Token Columns
                in_tokens_text,                # IN
                out_tokens_text,               # OUT
                total_tokens_text,             # TOTAL
                weight_text,                   # WEIGHT (ADDED)
            )

        log.info(f"Finished aggregating data for {len(self.sorted_task_ids)} unique tasks.")
        self.update_summary() # Update summary after loading tasks

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        """Formats duration in HH:MM:SS format. (Copied from Level)"""
        # TODO: Consider moving this to a shared utility module
        if seconds is None or seconds < 0:
            return "-"
        # Use Level's static method directly
        from geometor.seer.session.level import Level
        return Level._format_duration(seconds)

    def update_summary(self):
        """Updates the summary DataTables with aggregated data."""
        summary_table = self.query_one("#summary-table", DataTable)
        trials_table = self.query_one("#trials-table", DataTable)
        tokens_table = self.query_one("#tokens-table", DataTable) # Placeholder

        total_unique_tasks = len(self.tasks_summary)
        total_sessions_involved = set()
        total_errors = 0 # Keep this for the main table column aggregation logic if needed elsewhere
        tasks_failed_all_sessions = 0 # New counter for tasks failing in all their sessions
        # --- START: Counters for unique task passes ---
        unique_tasks_passed_test = 0
        unique_tasks_passed_train = 0
        # --- END: Counters for unique task passes ---
        grand_total_steps = 0
        grand_total_duration = 0.0
        best_scores = []
        # ADDED token counters for summary
        grand_total_prompt_tokens = 0
        grand_total_candidates_tokens = 0
        grand_total_tokens_all_tasks = 0
        grand_total_weight = 0 # ADDED total weight counter

        for task_id, data in self.tasks_summary.items():
            num_sessions_for_task = len(data['sessions'])
            task_error_count = data['errors'] # Now represents sessions with errors for this task

            total_sessions_involved.update(data['sessions'])
            # total_errors is no longer a simple sum of counts, but sum of sessions with errors
            total_errors += task_error_count

            # --- START: Check if task had errors in *any* session ---
            # tasks_failed_all_sessions is renamed/repurposed to count tasks that had at least one error
            if task_error_count > 0:
                tasks_failed_all_sessions += 1 # Count tasks that had errors in at least one session
            # --- END: Check if task had errors in *any* session ---

            # --- START: Increment unique task pass counters ---
            if data['test_passed'] > 0: # Check if task passed test at least once
                unique_tasks_passed_test += 1
            if data['train_passed'] > 0: # Check if task passed train at least once
                unique_tasks_passed_train += 1
            # --- END: Increment unique task pass counters ---
            # Keep aggregating total passes if needed elsewhere, but don't use for summary display
            total_test_passed = data['test_passed'] # Example: If you still need the raw total somewhere
            total_train_passed = data['train_passed'] # Example: If you still need the raw total somewhere
            grand_total_steps += data['total_steps']
            grand_total_duration += data['total_duration']
            if data['best_score'] != float('inf'):
                best_scores.append(data['best_score'])
            # ADDED token aggregation for summary
            grand_total_prompt_tokens += data['total_prompt_tokens']
            grand_total_candidates_tokens += data['total_candidates_tokens']
            grand_total_tokens_all_tasks += data['total_tokens']
            # ADDED weight aggregation for summary
            weight_val = data.get('weight', 0)
            if weight_val >= 0: # Only add valid weights
                grand_total_weight += weight_val

        num_sessions = len(total_sessions_involved)
        best_overall_score = f"{min(best_scores):.2f}" if best_scores else "-"
        formatted_total_duration = self._format_duration(grand_total_duration)

        # --- START Calculate summary percentages/diffs ---
        test_percent = (unique_tasks_passed_test / total_unique_tasks * 100) if total_unique_tasks > 0 else 0.0
        test_percent_str = f"{test_percent:.1f}%"

        train_diff = unique_tasks_passed_test - unique_tasks_passed_train
        train_diff_str = f"{train_diff:+}" # Format with sign (+/-)

        error_percent = (tasks_failed_all_sessions / total_unique_tasks * 100) if total_unique_tasks > 0 else 0.0
        error_percent_str = f"{error_percent:.1f}%"
        # --- END Calculate summary percentages/diffs ---

        # Clear and update summary table
        summary_table.clear()
        summary_table.add_row(Text("tasks:", justify="right"), Text(str(total_unique_tasks), justify="right"))
        summary_table.add_row(Text("sessions:", justify="right"), Text(str(num_sessions), justify="right"))
        summary_table.add_row(Text("steps:", justify="right"), Text(str(grand_total_steps), justify="right"))
        summary_table.add_row(Text("time:", justify="right"), Text(formatted_total_duration, justify="right"))
        summary_table.add_row(Text("weight:", justify="right"), Text(f"{grand_total_weight:,}", justify="right")) # ADDED total weight

        # Clear and update trials table using unique task pass counts and calculated stats
        trials_table.clear()
        trials_table.add_row(
            Text("test:", justify="right"),
            Text(str(unique_tasks_passed_test), justify="right"),
            Text(test_percent_str, justify="right") # Add percentage
        )
        trials_table.add_row(
            Text("train:", justify="right"),
            Text(str(unique_tasks_passed_train), justify="right"),
            Text(train_diff_str, justify="right") # Add difference
        )
        trials_table.add_row(
            Text("errors:", justify="right"),
            Text(str(tasks_failed_all_sessions), justify="right"), # Use the count of tasks with errors
            Text(error_percent_str, justify="right") # Add percentage
        )
        # Removed best score row

        # Clear and update tokens table
        # Clear and update tokens table (Placeholder - needs data aggregation)
        tokens_table.clear()
        tokens_table.add_row(Text("in:", justify="right"), Text(f"{grand_total_prompt_tokens:,}", justify="right"))
        tokens_table.add_row(Text("out:", justify="right"), Text(f"{grand_total_candidates_tokens:,}", justify="right"))
        tokens_table.add_row(Text("total:", justify="right"), Text(f"{grand_total_tokens_all_tasks:,}", justify="right"))


    def action_cursor_down(self) -> None:
        """Move the cursor down in the DataTable."""
        self.table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move the cursor up in the DataTable."""
        self.table.action_cursor_up()

    def action_select_task(self) -> None:
        """Called when a task row is selected (Enter or 'l'). Pushes TaskSessionsScreen."""
        # Ensure we target the correct table using its ID
        table = self.query_one("#tasks-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            log.warning("action_select_task: Table empty or no cursor row.")
            return # No tasks or no selection

        cursor_row = table.cursor_row
        log.info(f"action_select_task: Cursor row is {cursor_row}")

        try:
            # Get the entire row data using get_row_at
            row_data = table.get_row_at(cursor_row)
            if not row_data:
                 log.error(f"action_select_task: Could not get row data for row {cursor_row}.")
                 self.notify("Error selecting task row data.", severity="error")
                 return

            # The first element in the row data should be the task_id
            task_id = str(row_data[0]) # Ensure it's a string

            # Basic validation
            if not task_id:
                log.error(f"action_select_task: Retrieved empty task ID from row data at index {cursor_row}.")
                self.notify("Error: Could not get task ID from selected row.", severity="error")
                return

            log.info(f"action_select_task: Task ID from row data ({cursor_row}) is '{task_id}'. Pushing TaskSessionsScreen.")
            self.app.push_screen(TaskSessionsScreen(self.sessions_root, task_id))

        except IndexError:
            # This might happen if the row data structure is unexpected
            log.exception(f"action_select_task: IndexError accessing row data for row {cursor_row}.")
            self.notify("Error accessing task data.", severity="error")
        except Exception as e:
            # Catch other potential errors
            log.exception(f"action_select_task: Error processing row {cursor_row}: {e}")
            self.notify("Error selecting task.", severity="error")


    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Handle row selection via click."""
        self.action_select_task()

    def refresh_content(self) -> None:
        """Reloads task data and updates the screen."""
        log.info("Refreshing TasksScreen content...")
        # Store current cursor position
        current_cursor_row = self.table.cursor_row

        self.load_and_display_tasks() # Reloads table data and updates summary

        # Restore cursor position if possible
        if current_cursor_row is not None and 0 <= current_cursor_row < self.table.row_count:
            self.table.move_cursor(row=current_cursor_row, animate=False)
        elif self.table.row_count > 0:
            self.table.move_cursor(row=0, animate=False) # Move to top if previous row is gone

        self.table.focus() # Ensure table has focus

    # --- START REVISED SORT METHOD ---
    def perform_sort(self, sort_key: ColumnKey) -> None:
        """Sorts the task data and reloads the DataTable."""
        log.info(f"Performing sort on TasksScreen by key: {sort_key}")

        # Determine sort direction
        reverse = False
        if self.current_sort_key == sort_key:
            reverse = not self.current_sort_reverse
        else:
            # Default sort directions (can be customized per column if needed)
            # Typically descending for numeric/counts, ascending for names
            key_str = str(sort_key)
            if key_str in ["SESSIONS", "ERRORS", "TEST", "TRAIN", "STEPS", "BEST", "IN", "OUT", "TOTAL", "WEIGHT", "TIME"]:
                 reverse = True # Default descending for numeric-like columns
            else: # TASK
                 reverse = False # Default ascending for text

        self.current_sort_key = sort_key
        self.current_sort_reverse = reverse

        # Define key function operating directly on the summary data dict
        def get_sort_key_from_dict(item):
            task_id, data_dict = item
            key_str = str(sort_key)

            if key_str == "TASK":
                return task_id

            if key_str == "SESSIONS":
                # Sort by the number of sessions
                return len(data_dict.get('sessions', set()))

            if key_str == "ERRORS":
                # Sort by the count of sessions with errors for this task
                return data_dict.get('errors', 0)

            if key_str == "TEST":
                # Sort by count of sessions where test passed
                return data_dict.get('test_passed', 0)

            if key_str == "TRAIN":
                 # Sort by count of sessions where train passed
                return data_dict.get('train_passed', 0)

            if key_str == "STEPS":
                return data_dict.get('total_steps', 0)

            if key_str == "BEST":
                # Lower score is better, inf sorts last when ascending
                score = data_dict.get('best_score', float('inf'))
                # Return negative score for descending sort (highest score first)
                # Or handle inf appropriately if reverse=False (lowest score first)
                # Python's float('inf') comparison handles this correctly with reverse flag.
                return score

            if key_str == "TIME":
                # Sort by total duration in seconds
                duration = data_dict.get('total_duration', -1.0)
                return duration if duration is not None else -1.0

            if key_str == "IN":
                return data_dict.get('total_prompt_tokens', 0)

            if key_str == "OUT":
                return data_dict.get('total_candidates_tokens', 0)

            if key_str == "TOTAL":
                return data_dict.get('total_tokens', 0)

            if key_str == "WEIGHT":
                # Sort valid weights numerically. ERR/?: sort them last when descending, first when ascending.
                weight = data_dict.get('weight', -2) # Use -2 for not found/default
                if weight >= 0: return weight
                # Assign values that sort consistently relative to numbers based on 'reverse'
                # If reverse (desc), we want ERR/? to be effectively -inf
                # If not reverse (asc), we want ERR/? to be effectively +inf (or handle separately)
                # Let's use a simpler approach: map ERR/ ? to values that place them consistently.
                # Ascending: ERR (-1) < ? (-2) < 0 < positive weights.
                # Map: ERR -> float('-inf'), ? -> float('-inf') + 1
                if weight == -1: return float('-inf')      # ERR sorts first (ascending) / last (descending)
                if weight == -2: return float('-inf') + 1  # ? sorts after ERR (ascending) / before ERR (descending)
                return float('-inf') # Fallback for unexpected negative values

            # Fallback for unknown column
            log.error(f"Unknown sort key encountered: {key_str}")
            return None # Should not happen if modal uses table columns

        try:
            # 1. Get items from the summary dictionary
            items_to_sort = list(self.tasks_summary.items())

            # 2. Sort the items using the new key function
            # Handle potential None return from key function gracefully during sort
            items_to_sort.sort(key=lambda item: get_sort_key_from_dict(item) or 0, reverse=reverse)

            # 3. Update the order of task IDs
            self.sorted_task_ids = [item[0] for item in items_to_sort]

            # 4. Reload the table content using the new sorted order
            # load_and_display_tasks already calls self.table.clear()
            self.load_and_display_tasks()

            # Ensure the cursor is reset or maintained appropriately after sort
            if self.table.row_count > 0:
                self.table.move_cursor(row=0, animate=False) # Move cursor to top after sort

            self.notify(f"Sorted by {str(self.table.columns[sort_key].label)} {'(desc)' if reverse else '(asc)'}")

        except Exception as e:
            log.exception(f"Error during TasksScreen sort: {e}") # Use log.exception
            self.notify(f"Error sorting table: {e}", severity="error")
            # Restore default sort on error
            self.sorted_task_ids = sorted(self.tasks_summary.keys())
            # load_and_display_tasks already calls self.table.clear()
            self.load_and_display_tasks()
            if self.table.row_count > 0:
                 self.table.move_cursor(row=0, animate=False) # Reset cursor on error too
    # --- END REVISED SORT METHOD ---
