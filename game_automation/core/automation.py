from typing import Optional, Callable, Union
from .actions import VisualScript, VisualNode


class AutomationController:
    def __init__(self, scale_factor: float = 1.0):
        self.on_node_executed: Optional[Callable[[str, bool], None]] = None
        self.on_node_about_to_execute: Optional[Callable[[str], None]] = None
        self.scale_factor = float(scale_factor)
        self._loop_counters: dict[str, int] = {}
        self.execution_mode: str = "continuous"  # "continuous", "step", "paused"
        self.breakpoints: set[str] = set()
        self._execution_paused: bool = False
        self._waiting_for_step: bool = False
    
    def resume_execution(self):
        """Resume execution from pause or step mode"""
        self._execution_paused = False
    
    def pause_execution(self):
        """Pause execution"""
        self._execution_paused = True
    
    def toggle_breakpoint(self, node_id: str):
        """Toggle breakpoint on a node"""
        if node_id in self.breakpoints:
            self.breakpoints.remove(node_id)
        else:
            self.breakpoints.add(node_id)

    def execute_visual_script(self, script: VisualScript, vision_result: Union[dict, Callable[[], dict]], current_node_id: Optional[str] = None, should_cancel_callback: Optional[Callable[[], bool]] = None):
        # Reset loop counters at the start of each execution
        self._loop_counters.clear()
        
        # Handle empty script or missing starting node
        if not script.nodes:
            if self.on_node_executed:
                # Signal error condition
                self.on_node_executed("", False)
            raise ValueError("VisualScript has no nodes")
        
        nid = current_node_id or (script.nodes[0].id if script.nodes else None)
        if nid is None:
            if self.on_node_executed:
                # Signal error condition
                self.on_node_executed("", False)
            raise ValueError("VisualScript has no valid starting node")
        
        # Normalize vision_result to a callable if it's a dict
        if isinstance(vision_result, dict):
            _static_vision = vision_result
            get_vision_result = lambda: _static_vision
        else:
            get_vision_result = vision_result
        
        steps = 0
        visited = set()
        prev_loop_driven = False
        prev_node_id = None
        try:
            while nid and steps < 1000:
                # Check for cancellation before executing each node
                if should_cancel_callback and should_cancel_callback():
                    break
                
                # Check for global pause (applies to all execution modes)
                # This allows pause button to interrupt continuous execution
                if self._execution_paused:
                    self._wait_for_resume(should_cancel_callback)
                    # If cancelled during pause, break out of loop
                    if should_cancel_callback and should_cancel_callback():
                        break
                
                node = self._find_node(script, nid)
                if node is None:
                    # Node ID exists in connections but node not found in script
                    # Log error and break to prevent infinite loop
                    if self.on_node_executed:
                        self.on_node_executed(nid, False)
                    break
                
                allow_repeat = bool(node and (node.type == "loop" or prev_loop_driven))
                if nid in visited and not allow_repeat:
                    break
                visited.add(nid)
                steps += 1
                
                # Check for breakpoints and step mode
                if nid in self.breakpoints:
                    self._execution_paused = True
                    # Wait for resume with frequent cancellation checks
                    self._wait_for_resume(should_cancel_callback)
                
                if self.execution_mode == "step":
                    self._execution_paused = True
                    self._waiting_for_step = True
                    # Wait for step signal with frequent cancellation checks
                    self._wait_for_resume(should_cancel_callback)
                    self._waiting_for_step = False
                
                # Signal that we're about to execute this node (for running state)
                # This should be done via a callback if available
                if hasattr(self, 'on_node_about_to_execute') and self.on_node_about_to_execute:
                    self.on_node_about_to_execute(nid)
                
                ok = False
                next_override = None
                if node:
                    # Get fresh vision result for each node execution
                    current_vision = get_vision_result()
                    # Pass cancellation callback to _exec_node for cancellable operations
                    ok, next_override = self._exec_node(node, current_vision, should_cancel_callback=should_cancel_callback)
                if self.on_node_executed:
                    self.on_node_executed(nid, ok)
                
                prev_node_id = nid
                if node and node.type == "loop":
                    prev_loop_driven = (next_override == node.params.get("next_body"))
                else:
                    prev_loop_driven = False
                nid = next_override or script.connections.get(nid)
        finally:
            # Reset execution state to clean default regardless of how execution ended
            self.execution_mode = "continuous"
            self._execution_paused = False
            self._waiting_for_step = False

    def _wait_for_resume(self, should_cancel_callback: Optional[Callable[[], bool]] = None):
        """
        Wait for execution to resume (pause, breakpoint, or step mode).
        Continuously checks for cancellation to support stop button.
        
        This helper function is used by pause, breakpoint, and step mode to avoid code duplication.
        """
        import time
        while self._execution_paused and not (should_cancel_callback and should_cancel_callback()):
            time.sleep(0.05)  # Reduced sleep interval for faster cancellation response
            # Check cancellation more frequently
            if should_cancel_callback and should_cancel_callback():
                break
    
    def _find_node(self, script: VisualScript, nid: str) -> Optional[VisualNode]:
        for n in script.nodes:
            if n.id == nid:
                return n
        return None

    def _exec_node(self, node: VisualNode, vision_result: dict, should_cancel_callback: Optional[Callable[[], bool]] = None) -> tuple[bool, Optional[str]]:
        t = node.type
        if t == "sleep":
            import time
            secs = float(node.params.get("seconds", 0.2))
            # Break long sleep into smaller chunks to allow cancellation
            chunk_duration = 0.1  # Check cancellation every 100ms
            elapsed = 0.0
            while elapsed < secs:
                if should_cancel_callback and should_cancel_callback():
                    # Cancellation requested, return early
                    return False, None
                remaining = secs - elapsed
                sleep_time = min(chunk_duration, remaining)
                time.sleep(sleep_time)
                elapsed += sleep_time
            return True, None
        if t == "key":
            try:
                # Check cancellation before key press
                if should_cancel_callback and should_cancel_callback():
                    return False, None
                
                import pyautogui
                key = str(node.params.get("key", "space"))
                pyautogui.press(key)
                
                # Check cancellation after key press
                if should_cancel_callback and should_cancel_callback():
                    return False, None
                
                return True, None
            except Exception:
                return False, None
        if t == "click":
            try:
                import pyautogui
                m = node.params.get("mode", "label")
                if m == "label":
                    label = str(node.params.get("label", ""))
                    det = next((d for d in vision_result.get("found_targets", []) if d.get("label") == label), None)
                    if det:
                        x1, y1, x2, y2 = det["bbox"]
                        cx = int((x1 + x2) / 2 * self.scale_factor)
                        cy = int((y1 + y2) / 2 * self.scale_factor)
                        pyautogui.moveTo(cx, cy, duration=float(node.params.get("duration", 0)))
                        pyautogui.click(button=str(node.params.get("button", "left")))
                        return True, None
                return False, None
            except Exception:
                return False, None
        if t == "find_color":
            try:
                # Check cancellation before starting image processing
                if should_cancel_callback and should_cancel_callback():
                    return False, None
                
                from .image_processor import ImageProcessor
                frame_bgr = vision_result.get("frame")
                if frame_bgr is None:
                    return False, None
                hsv_min = node.params.get("hsv_min")
                hsv_max = node.params.get("hsv_max")
                bgr_min = node.params.get("bgr_min")
                bgr_max = node.params.get("bgr_max")
                ip = ImageProcessor()
                boxes = ip.find_color(frame_bgr, hsv_min=hsv_min, hsv_max=hsv_max, bgr_min=bgr_min, bgr_max=bgr_max)
                
                # Check cancellation after image processing completes
                if should_cancel_callback and should_cancel_callback():
                    return False, None
                
                return bool(boxes), None
            except Exception:
                return False, None
        if t == "condition":
            try:
                result = False
                m = node.params.get("mode", "label")
                if m == "label":
                    label = str(node.params.get("label", ""))
                    min_confidence = float(node.params.get("min_confidence", 0.0))
                    det = next((d for d in vision_result.get("found_targets", []) if d.get("label") == label), None)
                    if det:
                        det_confidence = det.get("confidence", 0.0)
                        result = det_confidence >= min_confidence
                    else:
                        result = False
                elif m == "color":
                    # Check cancellation before starting image processing
                    if should_cancel_callback and should_cancel_callback():
                        return False, None
                    
                    from .image_processor import ImageProcessor
                    frame_bgr = vision_result.get("frame")
                    if frame_bgr is not None:
                        hsv_min = node.params.get("hsv_min")
                        hsv_max = node.params.get("hsv_max")
                        bgr_min = node.params.get("bgr_min")
                        bgr_max = node.params.get("bgr_max")
                        ip = ImageProcessor()
                        boxes = ip.find_color(frame_bgr, hsv_min=hsv_min, hsv_max=hsv_max, bgr_min=bgr_min, bgr_max=bgr_max)
                        
                        # Check cancellation after image processing completes
                        if should_cancel_callback and should_cancel_callback():
                            return False, None
                        
                        result = bool(boxes)
                next_id = node.params.get("next_true") if result else node.params.get("next_false")
                return result, next_id
            except Exception:
                return False, None
        if t == "loop":
            try:
                count = int(node.params.get("count", 0))
                executed = self._loop_counters.get(node.id, 0)
                if executed < count:
                    self._loop_counters[node.id] = executed + 1
                    return True, node.params.get("next_body")
                else:
                    self._loop_counters.pop(node.id, None)
                    return True, node.params.get("next_after")
            except Exception:
                return False, None
        if t == "find_image":
            try:
                template_name = str(node.params.get("template_name", ""))
                confidence_threshold = float(node.params.get("confidence", 0.8))
                
                if not template_name:
                    return False, None
                
                # Check found_targets from vision_result
                found_targets = vision_result.get("found_targets", [])
                for det in found_targets:
                    if det.get("label") == template_name:
                        det_confidence = det.get("confidence", 0.0)
                        if det_confidence >= confidence_threshold:
                            return True, None
                
                return False, None
            except Exception:
                return False, None
        if t == "verify_image_color":
            try:
                # Check cancellation before starting verification
                if should_cancel_callback and should_cancel_callback():
                    return False, None
                
                template_name = str(node.params.get("template_name", ""))
                offset_x = int(node.params.get("offset_x", 0))
                offset_y = int(node.params.get("offset_y", 0))
                hsv_min = node.params.get("hsv_min")
                hsv_max = node.params.get("hsv_max")
                bgr_min = node.params.get("bgr_min")
                bgr_max = node.params.get("bgr_max")
                radius = float(node.params.get("radius", 0.0))
                
                if not template_name:
                    return False, None
                
                # Find the template in found_targets
                found_targets = vision_result.get("found_targets", [])
                det = next((d for d in found_targets if d.get("label") == template_name), None)
                if not det:
                    return False, None
                
                # Get bbox and calculate actual coordinates
                x1, y1, x2, y2 = det["bbox"]
                # Calculate center or use offset from top-left
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                check_x = center_x + offset_x
                check_y = center_y + offset_y
                
                # Get frame
                frame_bgr = vision_result.get("frame")
                if frame_bgr is None:
                    return False, None
                
                # Check bounds
                h, w = frame_bgr.shape[:2]
                if check_x < 0 or check_x >= w or check_y < 0 or check_y >= h:
                    return False, None
                
                # Extract a small ROI around the check point
                # Use radius as the ROI radius (half the side length of the square ROI)
                # ROI will be a square from (check_x - radius, check_y - radius) to (check_x + radius, check_y + radius)
                roi_size = max(1, int(radius) if radius > 0 else 5)
                roi_x1 = max(0, check_x - roi_size)
                roi_y1 = max(0, check_y - roi_size)
                roi_x2 = min(w, check_x + roi_size)
                roi_y2 = min(h, check_y + roi_size)
                roi = frame_bgr[roi_y1:roi_y2, roi_x1:roi_x2]
                
                if roi.size == 0:
                    return False, None
                
                # Check cancellation before image processing
                if should_cancel_callback and should_cancel_callback():
                    return False, None
                
                # Use ImageProcessor to find color in ROI
                from .image_processor import ImageProcessor
                ip = ImageProcessor()
                boxes = ip.find_color(roi, hsv_min=hsv_min, hsv_max=hsv_max, bgr_min=bgr_min, bgr_max=bgr_max)
                
                # Check cancellation after image processing completes
                if should_cancel_callback and should_cancel_callback():
                    return False, None
                
                return bool(boxes), None
            except Exception:
                return False, None
        return False, None

    def run_sequence(self, seq, vision_result: dict):
        for a in getattr(seq, "actions", []):
            t = a.type
            if t == "sleep":
                import time
                secs = float(a.params.get("seconds", 0.0))
                time.sleep(secs)
            elif t == "key":
                try:
                    import pyautogui
                    key = str(a.params.get("key", "space"))
                    pyautogui.keyDown(key)
                    pyautogui.keyUp(key)
                except Exception:
                    pass
            elif t == "click":
                try:
                    import pyautogui
                    mode = a.params.get("mode", "bbox")
                    if mode == "bbox":
                        x1, y1, x2, y2 = a.params.get("bbox", [0, 0, 0, 0])
                        cx = int((x1 + x2) / 2 * self.scale_factor)
                        cy = int((y1 + y2) / 2 * self.scale_factor)
                        pyautogui.moveTo(cx, cy, duration=float(a.params.get("duration", 0)))
                        pyautogui.click(button=str(a.params.get("button", "left")))
                    elif mode == "label":
                        label = str(a.params.get("label", ""))
                        det = next((d for d in vision_result.get("found_targets", []) if d.get("label") == label), None)
                        if det:
                            x1, y1, x2, y2 = det["bbox"]
                            cx = int((x1 + x2) / 2 * self.scale_factor)
                            cy = int((y1 + y2) / 2 * self.scale_factor)
                            pyautogui.moveTo(cx, cy, duration=float(a.params.get("duration", 0)))
                            pyautogui.click(button=str(a.params.get("button", "left")))
                except Exception:
                    pass
            elif t == "find_color":
                try:
                    import pyautogui
                    from .image_processor import ImageProcessor
                    frame_bgr = vision_result.get("frame")
                    if frame_bgr is None:
                        continue
                    hsv_min = a.params.get("hsv_min")
                    hsv_max = a.params.get("hsv_max")
                    bgr_min = a.params.get("bgr_min")
                    bgr_max = a.params.get("bgr_max")
                    ip = ImageProcessor()
                    boxes = ip.find_color(frame_bgr, hsv_min=hsv_min, hsv_max=hsv_max, bgr_min=bgr_min, bgr_max=bgr_max)
                    if boxes:
                        x1, y1, x2, y2 = boxes[0]
                        cx = int((x1 + x2) / 2 * self.scale_factor)
                        cy = int((y1 + y2) / 2 * self.scale_factor)
                        if bool(a.params.get("click", True)):
                            pyautogui.moveTo(cx, cy, duration=float(a.params.get("duration", 0)))
                            pyautogui.click(button=str(a.params.get("button", "left")))
                except Exception:
                    pass
            elif t == "verify_image_color":
                try:
                    from .image_processor import ImageProcessor
                    template_name = str(a.params.get("template_name", ""))
                    offset_x = int(a.params.get("offset_x", 0))
                    offset_y = int(a.params.get("offset_y", 0))
                    hsv_min = a.params.get("hsv_min")
                    hsv_max = a.params.get("hsv_max")
                    bgr_min = a.params.get("bgr_min")
                    bgr_max = a.params.get("bgr_max")
                    radius = float(a.params.get("radius", 0.0))
                    
                    if not template_name:
                        continue
                    
                    # Find the template in found_targets
                    found_targets = vision_result.get("found_targets", [])
                    det = next((d for d in found_targets if d.get("label") == template_name), None)
                    if not det:
                        continue
                    
                    # Get bbox and calculate actual coordinates
                    x1, y1, x2, y2 = det["bbox"]
                    # Calculate center or use offset from top-left
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    check_x = center_x + offset_x
                    check_y = center_y + offset_y
                    
                    # Get frame
                    frame_bgr = vision_result.get("frame")
                    if frame_bgr is None:
                        continue
                    
                    # Check bounds
                    h, w = frame_bgr.shape[:2]
                    if check_x < 0 or check_x >= w or check_y < 0 or check_y >= h:
                        continue
                    
                    # Extract a small ROI around the check point
                    roi_size = max(1, int(radius) if radius > 0 else 5)
                    roi_x1 = max(0, check_x - roi_size)
                    roi_y1 = max(0, check_y - roi_size)
                    roi_x2 = min(w, check_x + roi_size)
                    roi_y2 = min(h, check_y + roi_size)
                    roi = frame_bgr[roi_y1:roi_y2, roi_x1:roi_x2]
                    
                    if roi.size == 0:
                        continue
                    
                    # Use ImageProcessor to find color in ROI
                    ip = ImageProcessor()
                    boxes = ip.find_color(roi, hsv_min=hsv_min, hsv_max=hsv_max, bgr_min=bgr_min, bgr_max=bgr_max)
                    
                    # For legacy ActionSequence, we just verify and continue (no node control)
                    # The result can be logged or used for conditional logic in the sequence
                    if boxes:
                        # Verification successful - could log or perform additional actions here
                        pass
                    else:
                        # Verification failed - could log or skip remaining actions here
                        pass
                except Exception:
                    pass
