"""实时检查器 — 提供实时监控能力"""
from __future__ import annotations

import threading
import time
from .probe import get_probe


class Inspector:
    def __init__(self):
        self.probe = get_probe()
        self._running = False

    def start(self, interval: int = 3):
        self._running = True
        t = threading.Thread(target=self._loop, args=(interval,), daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def _loop(self, interval: int):
        while self._running:
            s = self.probe.get_stats()
            print(f"[probe] events={s['event_count']} errors={s['error_count']} uptime={s['uptime']:.0f}s")
            time.sleep(interval)


_inspector: Inspector | None = None


def start_inspector(interval: int = 3) -> Inspector:
    global _inspector
    if _inspector is None:
        _inspector = Inspector()
    _inspector.start(interval)
    return _inspector


def stop_inspector():
    if _inspector is not None:
        _inspector.stop()
