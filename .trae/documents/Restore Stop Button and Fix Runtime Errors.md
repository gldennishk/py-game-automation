I will modify `ui/main_window.py` to address the user's request and the reported errors:

1.  **Restore Start/Stop Buttons**:
    *   In `_build_ui`, I will remove the lines that hide `self.btn_start` and `self.btn_stop` (`setVisible(False)`), making them visible again for manual control.

2.  **Fix `AttributeError` in `run_current_sequence`**:
    *   When auto-starting capture, `self.last_vision_result` is initially `None` because the first frame hasn't been processed yet.
    *   I will update `run_current_sequence` to provide a default empty result (e.g., `{"found_targets": []}`) if `self.last_vision_result` is `None`, preventing the crash.

3.  **Fix `RuntimeError` on Exit**:
    *   I will add a `closeEvent` method to `MainWindow` to properly stop `self.capture_worker` when the application is closed. This prevents the background thread from trying to emit signals to a destroyed object.

This ensures the UI is usable (Stop button available), the script runs without crashing on startup, and the application closes cleanly.