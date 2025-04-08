# Implement Sortable and Filterable DataTables

**Goal:** Add sorting functionality to the DataTables used in various screens.

**Details:**
- Explore creating a reusable `SortableDataTable` wrapper component.
- This wrapper should handle the sorting logic and state.
- Consider managing the sort state separately from the underlying `DataTable` widget.
- Investigate performing sort operations externally, potentially similar to how dataframes manage sorting, to keep the `DataTable` focused on display.
- Include functionality to define data types for columns (e.g., string, number, date).
- Implement rendering logic based on data type, including:
    - Text alignment (e.g., right-align numbers).
    - Number formatting (e.g., decimal places, separators).
- Add filtering capabilities, potentially managed by the same wrapper component.
    - Allow users to filter rows based on column values.
    - Consider different filter types (text search, range selection, etc.).

**Status:** To Do
