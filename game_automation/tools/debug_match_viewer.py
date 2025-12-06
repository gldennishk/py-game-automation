import os
import time
from datetime import datetime

import cv2
import mss
import numpy as np

from core.targets import TARGET_DEFINITIONS


def grab_screen(region=None):
    with mss.mss() as sct:
        if region is None:
            monitor = sct.monitors[1]
        else:
            monitor = region
        img = sct.grab(monitor)
        frame = np.array(img)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


def main():
    region = None
    labels = list(TARGET_DEFINITIONS.keys())
    if not labels:
        print("[debug_match_viewer] No targets defined.")
        return
    idx = 0
    os.makedirs("debug_shots", exist_ok=True)
    print("[debug_match_viewer] n: next, p: prev, s: save, q: quit")
    while True:
        frame = grab_screen(region)
        H, W = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        label = labels[idx]
        cfg = TARGET_DEFINITIONS[label]
        tmpl_path = cfg["template"]
        threshold = float(cfg.get("threshold", 0.85))
        roi_ratio = cfg.get("roi", [0.0, 0.0, 1.0, 1.0])
        tmpl = cv2.imread(tmpl_path, cv2.IMREAD_GRAYSCALE)
        if tmpl is None:
            text = f"[{label}] template not found: {tmpl_path}"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("template_debug", frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('n'):
                idx = (idx + 1) % len(labels)
            elif key == ord('p'):
                idx = (idx - 1) % len(labels)
            continue
        th, tw = tmpl.shape[:2]
        x_min = int(roi_ratio[0] * W)
        y_min = int(roi_ratio[1] * H)
        x_max = int(roi_ratio[2] * W)
        y_max = int(roi_ratio[3] * H)
        x_min = max(0, x_min)
        y_min = max(0, y_min)
        x_max = min(W, x_max)
        y_max = min(H, y_max)
        if x_max - x_min < tw or y_max - y_min < th:
            cv2.putText(frame, f"[{label}] ROI too small", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("template_debug", frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('n'):
                idx = (idx + 1) % len(labels)
            elif key == ord('p'):
                idx = (idx - 1) % len(labels)
            continue
        roi_img = gray[y_min:y_max, x_min:x_max]
        t0 = time.perf_counter()
        res = cv2.matchTemplate(roi_img, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (255, 0, 0), 2)
        if max_val >= threshold:
            top_left = (max_loc[0] + x_min, max_loc[1] + y_min)
            bottom_right = (top_left[0] + tw, top_left[1] + th)
            cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)
        else:
            top_left = (max_loc[0] + x_min, max_loc[1] + y_min)
            cv2.circle(frame, top_left, 8, (0, 0, 255), 2)
        info1 = f"Label: {label}"
        info2 = f"max_val: {max_val:.3f}  threshold: {threshold:.3f}"
        info3 = f"latency: {latency_ms:.1f} ms  (n/p/s/q)"
        cv2.putText(frame, info1, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, info2, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, info3, (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.imshow("template_debug", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('n'):
            idx = (idx + 1) % len(labels)
        elif key == ord('p'):
            idx = (idx - 1) % len(labels)
        elif key == ord('s'):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join("debug_shots", f"{label}_{ts}.png")
            cv2.imwrite(filename, frame)
            print(f"[debug_match_viewer] saved {filename}")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

