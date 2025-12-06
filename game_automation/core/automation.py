from typing import Optional, Callable, Union
from .actions import VisualScript, VisualNode


class AutomationController:
    def __init__(self, scale_factor: float = 1.0):
        self.on_node_executed: Optional[Callable[[str, bool], None]] = None
        self.scale_factor = float(scale_factor)
        self._loop_counters: dict[str, int] = {}

    def execute_visual_script(self, script: VisualScript, vision_result: Union[dict, Callable[[], dict]], current_node_id: Optional[str] = None):
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
        while nid and steps < 1000:
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
            ok = False
            next_override = None
            if node:
                # Get fresh vision result for each node execution
                current_vision = get_vision_result()
                ok, next_override = self._exec_node(node, current_vision)
            if self.on_node_executed:
                self.on_node_executed(nid, ok)
            if node and node.type == "loop":
                prev_loop_driven = (next_override == node.params.get("next_body"))
            else:
                prev_loop_driven = False
            nid = next_override or script.connections.get(nid)

    def _find_node(self, script: VisualScript, nid: str) -> Optional[VisualNode]:
        for n in script.nodes:
            if n.id == nid:
                return n
        return None

    def _exec_node(self, node: VisualNode, vision_result: dict) -> tuple[bool, Optional[str]]:
        t = node.type
        if t == "sleep":
            import time
            secs = float(node.params.get("seconds", 0.2))
            time.sleep(secs)
            return True, None
        if t == "key":
            try:
                import pyautogui
                key = str(node.params.get("key", "space"))
                pyautogui.press(key)
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
                return bool(boxes), None
            except Exception:
                return False, None
        if t == "condition":
            try:
                result = False
                m = node.params.get("mode", "label")
                if m == "label":
                    label = str(node.params.get("label", ""))
                    det = next((d for d in vision_result.get("found_targets", []) if d.get("label") == label), None)
                    result = det is not None
                elif m == "color":
                    from .image_processor import ImageProcessor
                    frame_bgr = vision_result.get("frame")
                    if frame_bgr is not None:
                        hsv_min = node.params.get("hsv_min")
                        hsv_max = node.params.get("hsv_max")
                        bgr_min = node.params.get("bgr_min")
                        bgr_max = node.params.get("bgr_max")
                        ip = ImageProcessor()
                        boxes = ip.find_color(frame_bgr, hsv_min=hsv_min, hsv_max=hsv_max, bgr_min=bgr_min, bgr_max=bgr_max)
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
