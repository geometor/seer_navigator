from typing import List
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static, Header, Footer
from textual.binding import Binding
from textual.reactive import reactive
from textual import log

# Import a renderer for the grid
try:
    from geometor.seer_navigator.renderers.solid_grid import SolidGrid
except ImportError:
    log.error("Could not import SolidGrid renderer")
    
    # Define a simple fallback
    class SolidGrid(Static):
        def __init__(self, grid, **kwargs):
            super().__init__(**kwargs)
            self.grid = grid
            
        def render(self):
            from rich.text import Text
            text = Text()
            
            for row in self.grid:
                line = Text()
                for cell_value in row:
                    # Simple rendering with plain text numbers
                    line.append(f"{cell_value} ")
                text.append(line)
                text.append("\n")
            
            return text


class SimpleGridDisplay(App):
    """Simple app to display a grid centered on the screen with arrow key navigation."""
    
    CSS = """
    #grid-container {
        align: center middle;
        width: 100%;
        height: 100%;
        content-align: center middle;
    }
    
    SolidGrid {
        /* This ensures the grid widget itself centers its content */
        content-align: center middle;
    }
    
    #grid-info {
        color: $text;
        text-align: center;
        margin: 1 0;
    }
    """
    
    # Define keyboard bindings for navigation
    BINDINGS = [
        Binding("left,up", "show_input", "Input Grid"),
        Binding("right,down", "show_output", "Output Grid"),
        Binding("q", "quit", "Quit"),
    ]
    
    # Track which grid is currently being displayed
    showing_input = reactive(True)
    
    def __init__(self, input_grid: List[List[int]], output_grid: List[List[int]]):
        super().__init__()
        self.input_grid = input_grid
        self.output_grid = output_grid
        # Start with input grid
        self.current_grid = input_grid
        
    def compose(self) -> ComposeResult:
        """Create the UI layout with a centered grid."""
        yield Header(show_clock=True)
        
        # Status indicator for which grid is showing
        yield Static("Input Grid (use arrow keys to switch)", id="grid-info")
        
        # Create a container that will center its content
        with Container(id="grid-container"):
            # Directly yield the grid widget with input grid
            yield SolidGrid(self.current_grid)
            
        yield Footer()
        
    def on_mount(self) -> None:
        """Setup the app when mounted."""
        self.title = "Grid Viewer - Input/Output"
        
    def watch_showing_input(self, showing_input: bool) -> None:
        """React to changes in which grid is being shown."""
        # Update the grid data
        grid_widget = self.query_one(SolidGrid)
        
        # Update the grid data
        current_grid = self.input_grid if showing_input else self.output_grid
        grid_widget.grid = current_grid
        
        # Force the grid to re-render by calling update with the rendered content
        rendered_content = grid_widget.render()
        grid_widget.update(rendered_content)
        
        # Update the info text
        info_widget = self.query_one("#grid-info", Static)
        info_widget.update("Input Grid (use arrow keys to switch)" if showing_input else 
                           "Output Grid (use arrow keys to switch)")
        
    def action_show_input(self) -> None:
        """Switch to showing the input grid."""
        if not self.showing_input:
            self.showing_input = True
            
    def action_show_output(self) -> None:
        """Switch to showing the output grid."""
        if self.showing_input:
            self.showing_input = False


def main():
    # Sample input grid (checkerboard pattern)
    input_grid = [
        [0, 1, 0, 1, 0],
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0],
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0]
    ]
    
    # Sample output grid (inverted pattern)
    output_grid = [
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0],
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0],
        [1, 0, 1, 0, 1]
    ]
    
    try:
        # Try loading from task file if possible (simplified example)
        from pathlib import Path
        from geometor.seer.tasks.tasks import Tasks
        
        script_dir = Path(__file__).parent
        task_file = script_dir / "task.json"
        
        if task_file.exists():
            log.info(f"Loading task from {task_file}")
            tasks = Tasks(script_dir)
            if tasks and tasks[0].train:
                # Use first training pair from first task
                first_train_pair = tasks[0].train[0]
                input_grid = first_train_pair.input.grid.tolist()
                output_grid = first_train_pair.output.grid.tolist()
                log.info(f"Loaded grids from task '{tasks[0].id}'")
    except Exception as e:
        log.error(f"Failed to load task: {e}")
        log.info("Using sample grids instead")
    
    # Create and run the app
    app = SimpleGridDisplay(input_grid, output_grid)
    app.run()


if __name__ == "__main__":
    main()
