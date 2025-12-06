I will modify `game_automation/ui/widgets.py` to enhance the `ActionSequenceEditor` with a Label selection dropdown.

1.  **Import `TARGET_DEFINITIONS`**:
    *   In `game_automation/ui/widgets.py`, I will import `TARGET_DEFINITIONS` from `core.targets`.

2.  **Update `_append_row_for_action`**:
    *   Instead of just a `QLineEdit` in column 1 (Params), I will create a composite widget containing:
        *   The existing `QLineEdit` (for JSON text).
        *   A new `QComboBox` populated with keys from `TARGET_DEFINITIONS`.
    *   When a label is selected from the dropdown, it will automatically update the `QLineEdit` with the JSON string: `{"mode": "label", "label": "SELECTED_LABEL", "button": "left"}`.
    *   I will also handle the "Wait" action type request by adding "wait" to the action type dropdown if it's not already there, or just stick to "click/key/sleep" as per current implementation but ensure the dropdown helps with "click" actions specifically. (The user mentioned "wait_for" but then said "currently we have sleep", so I will focus on the "click" action optimization first as requested).

3.  **Update `_table_to_actions`**:
    *   Since the cell widget is now a container, I will update the logic to retrieve the text from the child `QLineEdit` correctly.

This plan directly addresses the user's request to make JSON generation easier by selecting a label.