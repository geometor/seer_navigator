import random
import time
from pathlib import Path
from typing import List, Tuple, Type, Optional, Any
import copy # For deep copying grid state

from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Header, Footer, Static
from textual import log

# --- Grid Parsing & Task Loading ---
# Assuming string_to_grid is available and returns a Grid object with a .grid attribute (list of lists)
try:
    from geometor.seer.tasks.grid import string_to_grid, Grid as SeerGrid
    from geometor.seer.tasks.tasks import Tasks # Import Tasks
except ImportError:
    log.error("Failed to import Grid or Tasks from geometor.seer.tasks")
    # Define dummies if needed for basic structure, but loading/parsing will fail
    class SeerGrid:
        def __init__(self, grid_data):
            self.grid = grid_data
    def string_to_grid(s: str) -> Optional[SeerGrid]:
        try:
            return SeerGrid([[int(c) for c in row.split()] for row in s.strip().split('\n')])
        except Exception:
            return None

# --- Renderers ---
try:
    from geometor.seer_navigator.renderers import (
        BaseGrid, SolidGrid, CharGrid, BlockGrid, TinyGrid
    )
    # Define the cycle order
    RENDERERS: List[Type[BaseGrid]] = [SolidGrid, CharGrid, BlockGrid, TinyGrid]
except ImportError:
    log.error("Could not import grid renderers. Grid visualization will fail.")
    # Define dummy classes if import fails
    class DummyGridWidget(Static):
        def __init__(self, grid_data: Any, *args, **kwargs):
            super().__init__("Renderer Import Error", *args, **kwargs)
    RENDERERS: List[Type[Static]] = [DummyGridWidget] # Use Static as base type hint
    BaseGrid = Static # Type hint alias

DEFAULT_INTERVAL = 0.05 # Animation speed (seconds per step)

class GridAnimator(Static):
    """Widget to display and animate the grid transition."""

    input_grid: reactive[List[List[int]]] = reactive([])
    output_grid: reactive[List[List[int]]] = reactive([])
    current_grid_state: reactive[List[List[int]]] = reactive([])
    renderer_class: reactive[Type[BaseGrid]] = reactive(RENDERERS[0]) # Start with the first renderer
    animating: reactive[bool] = reactive(False)
    _renderer: Optional[BaseGrid] = None # Initialize renderer instance variable

    def __init__(self, input_g: List[List[int]], output_g: List[List[int]], **kwargs):
        super().__init__(**kwargs)
        self.input_grid = input_g
        self.output_grid = output_g
        self._diff_indices: List[Tuple[int, int]] = []
        self._animation_timer = None
        self.interval = DEFAULT_INTERVAL
        # Initialize current_grid_state directly in __init__
        self.current_grid_state = copy.deepcopy(input_g)
        # Renderer will be initialized in on_mount via update_display

    def _initialize_renderer(self) -> None:
        """Initialize the renderer instance."""
        try:
            # Create a new renderer instance with the grid as first argument
            self._renderer = self.renderer_class(self.current_grid_state)
            log.info(f"Successfully created renderer: {self.renderer_class.__name__}")
        except Exception as e:
            log.error(f"Failed to initialize renderer: {e}", exc_info=True)
            self._renderer = None

    def on_mount(self) -> None:
        """Initialize state when mounted."""
        # Calculate differences between input and output grids
        self._diff_indices = self._calculate_diff()
        self.animating = False
        
        # Update the display
        self.update_display()
        
        # Set UI elements if app is available
        if hasattr(self, 'app') and self.app:
            renderer_name = getattr(self.renderer_class, '__name__', 'Unknown')
            self.app.sub_title = f"Ready ({renderer_name})"
            
            # Notify if grids are identical
            if not self._diff_indices:
                self.app.notify("Input and Output grids are identical.")

    def _calculate_diff(self) -> List[Tuple[int, int]]:
        """Find coordinates where input and output grids differ."""
        diff = []
        if not self.input_grid or not self.output_grid:
            return []
        rows = len(self.input_grid)
        cols = len(self.input_grid[0])
        for r in range(rows):
            for c in range(cols):
                if self.input_grid[r][c] != self.output_grid[r][c]:
                    diff.append((r, c))
        log.info(f"Calculated {len(diff)} differing cells.")
        return diff

    def update_display(self) -> None:
        """Update the display with the current grid state."""
        if not self.current_grid_state:
            self.update("Grid data is empty.")
            return
            
        try:
            if self._renderer is None:
                self._initialize_renderer()
                
            if self._renderer:
                # Set the grid data on the existing renderer
                self._renderer.grid = self.current_grid_state
                
                # Get the rendered content
                if hasattr(self._renderer, 'render'):
                    content = self._renderer.render()
                    self.update(content)
                else:
                    # If it doesn't have a render method, update with simple text
                    grid_text = "\n".join(" ".join(str(cell) for cell in row) for row in self.current_grid_state)
                    self.update(f"Grid Data:\n{grid_text}")
            else:
                # Fallback if renderer creation failed
                grid_text = "\n".join(" ".join(str(cell) for cell in row) for row in self.current_grid_state)
                self.update(f"Renderer Error - Using Text Display:\n\n{grid_text}")
        except Exception as e:
            log.error(f"Display update error: {e}", exc_info=True)
            self.update(f"Error updating display: {e}")

    # Watch for changes to renderer_class
    def watch_renderer_class(self, old_class, new_class) -> None:
        """Update renderer when class changes."""
        log.info(f"Renderer changed to: {new_class.__name__}")
        # Create a new renderer instance with the new class
        try:
            self._renderer = new_class(self.current_grid_state)
            self.update_display()
        except Exception as e:
            log.error(f"Error creating new renderer: {e}", exc_info=True)
            self._renderer = None
            grid_text = "\n".join(" ".join(str(cell) for cell in row) for row in self.current_grid_state)
            self.update(f"Renderer Creation Error: {e}\n\n{grid_text}")

    # Watch for changes to current_grid_state
    def watch_current_grid_state(self, old_state, new_state) -> None:
        """Update display when grid state changes."""
        if new_state:
            self.update_display()

    # Animation methods - unchanged
    def step_animation(self) -> None:
        """Perform one step of the animation."""
        if not self._diff_indices:
            self.pause_animation()
            log.info("Animation finished.")
            if hasattr(self, 'app') and self.app:
                self.app.notify("Animation finished.")
            return

        # Pick a random differing cell
        idx_to_change = random.choice(range(len(self._diff_indices)))
        r, c = self._diff_indices.pop(idx_to_change)

        # Update the current grid state
        new_grid_state = [row[:] for row in self.current_grid_state]
        new_grid_state[r][c] = self.output_grid[r][c]
        self.current_grid_state = new_grid_state

    def start_animation(self) -> None:
        """Start or resume the animation timer."""
        if not self.animating and self._diff_indices:
            log.info("Starting animation.")
            self.animating = True
            if self._animation_timer:
                self._animation_timer.resume()
            else:
                self._animation_timer = self.set_interval(self.interval, self.step_animation)
            if hasattr(self, 'app') and self.app:
                renderer_name = getattr(self.renderer_class, '__name__', 'Unknown')
                self.app.sub_title = f"Animating ({renderer_name}) - Speed: {self.interval:.2f}s"
        elif not self._diff_indices:
            log.info("Animation already finished or no differences.")
            if hasattr(self, 'app') and self.app:
                self.app.notify("Animation finished or grids are identical.")

    def pause_animation(self) -> None:
        """Pause the animation timer."""
        if self.animating:
            log.info("Pausing animation.")
            self.animating = False
            if self._animation_timer:
                self._animation_timer.pause()
            if hasattr(self, 'app') and self.app:
                renderer_name = getattr(self.renderer_class, '__name__', 'Unknown')
                self.app.sub_title = f"Paused ({renderer_name})"

    def reset_animation(self) -> None:
        """Reset the animation to the initial state."""
        log.info("Resetting animation.")
        self.pause_animation()
        if self._animation_timer:
            self._animation_timer.stop()
            self._animation_timer = None

        self.current_grid_state = copy.deepcopy(self.input_grid)
        self._diff_indices = self._calculate_diff()
        self.animating = False
        self.update_display()
        if hasattr(self, 'app') and self.app:
            renderer_name = getattr(self.renderer_class, '__name__', 'Unknown')
            self.app.sub_title = f"Ready ({renderer_name})"
        if not self._diff_indices and hasattr(self, 'app') and self.app:
            self.app.notify("Input and Output grids are identical.")

    def set_speed(self, interval: float):
        """Change animation speed."""
        self.interval = max(0.01, interval)
        log.info(f"Animation speed set to {self.interval:.3f}s")
        if self.animating:
            self.pause_animation()
            if self._animation_timer:
                self._animation_timer.stop()
                self._animation_timer = None
            self.start_animation()
        elif hasattr(self, 'app') and self.app:
            renderer_name = getattr(self.renderer_class, '__name__', 'Unknown')
            self.app.sub_title = f"Paused ({renderer_name}) - Speed: {self.interval:.2f}s"


# --- Textual App ---
class GridAnimatorApp(App):
    """Textual app to animate grid transitions."""

    CSS_PATH = None # Add if you have specific CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_animation", "Start/Pause"),
        Binding("r", "reset_animation", "Reset"),
        Binding("n", "cycle_renderer", "Next Renderer"),
        Binding("p", "prev_renderer", "Prev Renderer"),
        Binding("+", "speed_up", "Faster"),
        Binding("-", "slow_down", "Slower"),
    ]

    def __init__(self, input_grid_data: List[List[int]], output_grid_data: List[List[int]]):
        super().__init__()
        self.input_grid_data = input_grid_data
        self.output_grid_data = output_grid_data
        self.renderer_index = 0

    def compose(self) -> ComposeResult:
        yield Header()
        # Pass initial data to the animator widget
        yield GridAnimator(self.input_grid_data, self.output_grid_data, id="grid-animator")
        yield Footer()

    def on_mount(self) -> None:
        """Set initial title."""
        self.title = "Grid Transition Animator"
        self.sub_title = f"Ready ({RENDERERS[self.renderer_index].__name__})"

    # --- Actions ---
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_toggle_animation(self) -> None:
        """Start or pause the animation."""
        animator = self.query_one(GridAnimator)
        if animator.animating:
            animator.pause_animation()
        else:
            animator.start_animation()

    def action_reset_animation(self) -> None:
        """Reset the animation to the beginning."""
        animator = self.query_one(GridAnimator)
        animator.reset_animation()

    def action_cycle_renderer(self) -> None:
        """Switch to the next renderer."""
        self.renderer_index = (self.renderer_index + 1) % len(RENDERERS)
        animator = self.query_one(GridAnimator)
        animator.renderer_class = RENDERERS[self.renderer_index]
        # Update subtitle
        state = "Animating" if animator.animating else ("Paused" if animator._animation_timer else "Ready")
        self.sub_title = f"{state} ({animator.renderer_class.__name__}) - Speed: {animator.interval:.2f}s"

    def action_prev_renderer(self) -> None:
        """Switch to the previous renderer."""
        self.renderer_index = (self.renderer_index - 1 + len(RENDERERS)) % len(RENDERERS)
        animator = self.query_one(GridAnimator)
        animator.renderer_class = RENDERERS[self.renderer_index]
        # Update subtitle
        state = "Animating" if animator.animating else ("Paused" if animator._animation_timer else "Ready")
        self.sub_title = f"{state} ({animator.renderer_class.__name__}) - Speed: {animator.interval:.2f}s"

    def action_speed_up(self) -> None:
        """Decrease animation interval (faster)."""
        animator = self.query_one(GridAnimator)
        animator.set_speed(animator.interval / 1.5) # Decrease interval

    def action_slow_down(self) -> None:
        """Increase animation interval (slower)."""
        animator = self.query_one(GridAnimator)
        animator.set_speed(animator.interval * 1.5) # Increase interval


# --- Main Execution ---
def main():
    script_dir = Path(__file__).parent
    task_file = script_dir / "task.json"

    print(f"Looking for task file: {task_file}")

    if not task_file.exists():
        print(f"Error: task.json not found in {script_dir}")
        log.error(f"task.json not found in {script_dir}")
        return

    try:
        print("Loading task...")
        # Tasks expects a folder path, so give it the script's directory
        tasks = Tasks(script_dir)
        if not tasks:
            print("Error: No tasks found or loaded from the directory.")
            log.error("No tasks found or loaded from the directory containing task.json.")
            return

        # Assume the first task and its first training pair
        task = tasks[0]
        if not task.train:
            print(f"Error: Task '{task.id}' has no training pairs.")
            log.error(f"Task '{task.id}' has no training pairs.")
            return

        first_train_pair = task.train[0]
        input_grid = first_train_pair.input.grid.tolist() # Get as list of lists
        output_grid = first_train_pair.output.grid.tolist() # Get as list of lists
        task_id = task.id
        print(f"Loaded task '{task_id}', using first training pair.")
        log.info(f"Loaded task '{task_id}', using first training pair.")

    except ImportError:
        print("Error: Failed to import necessary geometor modules (Tasks/Grid). Cannot load task.")
        log.critical("Failed to import necessary geometor modules (Tasks/Grid).")
        return
    except Exception as e:
        print(f"Error loading or processing task.json: {e}")
        log.exception(f"Error loading or processing {task_file}: {e}")
        return

    # Validate dimensions (already numpy arrays in TaskPair, convert back for App)
    if not input_grid or not output_grid:
         print("One or both grids are empty after loading from task. Exiting.")
         log.error("Input or output grid is empty after loading from task.")
         return

    rows_in, cols_in = len(input_grid), len(input_grid[0])
    rows_out, cols_out = len(output_grid), len(output_grid[0])

    if rows_in != rows_out or cols_in != cols_out:
        print(f"Grid dimensions from task do not match! Input: {rows_in}x{cols_in}, Output: {rows_out}x{cols_out}. Exiting.")
        log.error(f"Grid dimensions mismatch in task '{task_id}': Input {rows_in}x{cols_in}, Output {rows_out}x{cols_out}")
        return

    print(f"Grids loaded ({rows_in}x{cols_in}) from task '{task_id}'. Starting Textual app...")
    app = GridAnimatorApp(input_grid, output_grid)
    app.run()

if __name__ == "__main__":
    main()
