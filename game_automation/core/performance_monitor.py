import time
from collections import deque
import psutil


class PerformanceMonitor:
    def __init__(self, window_seconds: float = 1.0):
        self.window = window_seconds
        self.timestamps = deque()

    def tick(self, ts: float):
        self.timestamps.append(ts)
        cutoff = ts - self.window
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()

    def fps(self) -> float:
        n = len(self.timestamps)
        if n <= 1:
            return 0.0
        duration = self.timestamps[-1] - self.timestamps[0]
        if duration <= 0:
            return 0.0
        return (n - 1) / duration

    def resources(self):
        mem = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)
        return {
            "cpu_percent": cpu_percent,
            "mem_used": mem.used,
            "mem_total": mem.total,
            "mem_percent": mem.percent,
        }

