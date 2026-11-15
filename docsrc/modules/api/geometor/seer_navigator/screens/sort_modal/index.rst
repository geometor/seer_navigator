geometor.seer_navigator.screens.sort_modal
==========================================

.. py:module:: geometor.seer_navigator.screens.sort_modal

.. autoapi-nested-parse::

   Defines the SortModal screen for selecting a DataTable column to sort.



Classes
-------

.. autoapisummary::

   geometor.seer_navigator.screens.sort_modal.SortModal


Module Contents
---------------

.. py:class:: SortModal(columns: Dict[textual.widgets._data_table.ColumnKey, object], *args, **kwargs)

   Bases: :py:obj:`textual.screen.ModalScreen`\ [\ :py:obj:`Union`\ [\ :py:obj:`textual.widgets._data_table.ColumnKey`\ , :py:obj:`None`\ ]\ ]


   Modal dialog for selecting a column to sort. Returns the selected ColumnKey or None.


   .. py:attribute:: CSS
      :value: Multiline-String

      .. raw:: html

         <details><summary>Show Value</summary>

      .. code-block:: python

         """
             SortModal {
                 align: center middle;
             }
         
             #dialog { /* Changed ID and styling */
                 padding: 0 1;
                 width: auto; /* Auto width based on content */
                 max-width: 60; /* Limit max width */
                 height: auto; /* Auto height based on content */
                 max-height: 80%; /* Limit max height */
                 border: thick $background 80%;
                 background: $surface;
             }
         
             #dialog > Label { /* Style title label */
                 width: 100%;
                 text-align: center;
                 margin-bottom: 1;
             }
         
             #sort-list { /* Style the ListView */
                 border: none;
                 background: $surface;
                 height: auto; /* Adjust height based on content */
                 max-height: 15; /* Limit max height to prevent overflow */
             }
         
             #sort-list > ListItem {
                 padding: 0 1; /* Remove vertical padding, keep horizontal */
                 height: 1; /* Explicitly set height to 1 */
             }
         
             #sort-list > ListItem.--highlight {
                 background: $accent;
             }
             """

      .. raw:: html

         </details>




   .. py:attribute:: BINDINGS


   .. py:attribute:: column_options
      :type:  List[Tuple[str, textual.widgets._data_table.ColumnKey]]
      :value: []



   .. py:method:: compose() -> textual.app.ComposeResult


   .. py:method:: handle_selection(event: textual.widgets.ListView.Selected) -> None

      Handle selection of a column from the ListView.



   .. py:method:: action_cancel_sort() -> None

      Called when escape is pressed.



