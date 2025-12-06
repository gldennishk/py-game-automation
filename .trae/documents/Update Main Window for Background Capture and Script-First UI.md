I will modify `ui/main_window.py` to implement the requested changes:

1.  **Set Script Tab as Default & Hide Capture Buttons**:
    *   In `_build_ui`, after creating the tabs, I will set the current widget to `self.script_editor`.
    *   I will also set `self.btn_start` and `self.btn_stop` to be invisible (`setVisible(False)`), as they are no longer the primary way to control capture.

2.  **Disable Preview Rendering**:
    *   In `on_frame`, I will comment out the code responsible for converting the frame to `QImage` and updating `self.preview_label`. This ensures the background capture and image processing continue without updating the GUI with the video feed.

3.  **Auto-start Capture on Run Script**:
    *   In `run_current_sequence`, I will remove the check that blocks execution if `self.last_vision_result` is missing.
    *   I will add logic to check if `self.capture_worker` is `None`. If it is, I will call `self.start_capture()` to automatically start the background screen capture.

This aligns with your goal of having a background-only capture system that is driven by the Script execution.