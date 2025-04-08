# Research Report: Improving DataTable Data Handling in Seer Navigator

**Date:** 2025-04-07

## Introduction

This report evaluates the potential benefits and drawbacks of adopting more robust data structures, specifically Pandas DataFrames or similar alternatives (e.g., Polars, lists of Pydantic models/dataclasses), as the primary source for data displayed in Textual `DataTable` widgets within the `seer-navigator` application.

Currently, data loading, structuring, sorting, and potential filtering for `DataTable` instances appear to be handled manually within individual screen components (e.g., `SessionsScreen`, `TaskScreen`, `TasksScreen`, `TaskSessionsScreen`). This often involves custom sorting functions (`perform_sort`, `get_sort_key`) and manual data aggregation.

## Proposed Strategy: Using Structured Data Objects (e.g., DataFrames)

The proposed strategy is to refactor the data handling logic to use a dedicated data structure library like Pandas before populating the `DataTable`. The typical workflow would be:

1.  Load raw data (from JSON files, directory listings, etc.).
2.  Transform and structure this data into a DataFrame (or similar object).
3.  Perform necessary operations like sorting, filtering, or aggregation directly on the DataFrame using the library's optimized functions.
4.  Extract the processed data from the DataFrame in a format suitable for `DataTable.add_rows()`.
5.  Populate the `DataTable` with this processed data.

## Advantages

*   **Simplified Sorting:** Leverage powerful, built-in sorting capabilities (`df.sort_values()`) that handle multiple columns, data types, and directions efficiently, eliminating repetitive custom sort logic in each screen.
*   **Robust Filtering:** Implement data filtering using concise and expressive library functions (`df.query()`, boolean indexing), simplifying features like search or data subset display.
*   **Data Type Consistency:** DataFrames enforce data types per column, preventing common errors related to sorting or comparing mixed types (e.g., strings vs. numbers).
*   **Efficient Aggregation:** Simplify complex data aggregation tasks (e.g., in `TasksScreen`) using built-in functions (`groupby`, `agg`).
*   **Code Reduction & Reusability:** Consolidate data manipulation logic, reducing boilerplate code across multiple screens and improving maintainability.
*   **Potentially Easier Data Loading:** Libraries often provide convenient functions to load data directly from various file formats (CSV, JSON).

## Disadvantages & Considerations

*   **Dependency Management:** Introduces a new dependency (e.g., Pandas, Polars). Pandas, in particular, is a relatively large library. The impact on installation size and environment complexity should be considered.
*   **Learning Curve:** Requires familiarity with the chosen library's API.
*   **Integration Effort:** Requires refactoring existing data loading and display logic across multiple screens.
*   **Minor Overhead:** For very small datasets, there might be a slight performance overhead compared to using basic Python lists, although likely negligible in a TUI context.

## Conclusion & Recommendation

Adopting a structured data object approach, particularly using a library like Pandas, offers significant advantages for the `seer-navigator` project. The benefits of simplified sorting, robust filtering, improved data consistency, and reduced code duplication appear to outweigh the cost of adding a dependency and the initial refactoring effort.

**Recommendation:** Proceed with refactoring the data handling for `DataTable` widgets to utilize Pandas DataFrames. This will likely lead to more maintainable, robust, and feature-rich code in the long run. Start with one screen (e.g., `SessionsScreen`) as a proof-of-concept.
