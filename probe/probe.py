"""AgiCode 探针核心 — 实时监控和调试"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from collections import deque
from typing import Any


class Probe:
    """AgiCode 探针主类（单例）"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str | Path | None = None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.events: deque = deque(maxlen=10000)
        self.session_id = f"sess_{int(time.time())}"
        self.start_time = time.time()
        self._event_count = 0
        self._error_count = 0
        self.lock = threading.Lock()
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self._recording = True
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()

    def record_event(self, event_type: str, data: dict) -> dict:
        with self.lock:
            self._event_count += 1
            ev = {
                "id": self._event_count, "session": self.session_id,
                "ts": datetime.now().isoformat(), "elapsed": round(time.time() - self.start_time, 3),
                "type": event_type, "data": data,
            }
            self.events.append(ev)
        return ev

    def record_error(self, error: Exception, context: dict | None = None) -> dict:
        self._error_count += 1
        return self.record_event("error", {
            "type": type(error).__name__, "message": str(error),
            "context": context or {},
            "traceback": traceback.format_exc()[-2000:] if hasattr(traceback, 'format_exc') else "",
        })

    def record_tool_call(self, tool_name: str, args: dict, result: Any, duration: float) -> dict:
        return self.record_event("tool_call", {
            "tool": tool_name, "args": args,
            "result": str(result)[:500], "duration": round(duration, 3),
            "slow": duration > 3.0,
        })

    def get_stats(self) -> dict:
        return {
            "session": self.session_id,
            "uptime": round(time.time() - self.start_time, 1),
            "event_count": self._event_count,
            "error_count": self._error_count,
            "queue": len(self.events),
        }

    def get_recent_events(self, limit: int = 50) -> list:
        return list(self.events)[-limit:]

    def get_errors(self, limit: int = 20) -> list:
        return [e for e in self.events if e.get("type") == "error"][-limit:]

    def get_summary(self) -> dict:
        by_type = {}
        for e in self.events:
            t = e.get("type", "?")
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "session": self.session_id, "uptime": round(time.time() - self.start_time, 1),
            "total_events": self._event_count, "total_errors": self._error_count,
            "events_by_type": by_type,
        }

    def close(self):
        self._recording = False
        f = self.log_dir / f"probe_{self.session_id}.json"
        try:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump({"events": list(self.events)}, fp, ensure_ascii=False)
        except Exception:
            pass

    def _flush_loop(self):
        while self._recording:
            time.sleep(10)


_probe: Probe | None = None


def get_probe() -> Probe:
    global _probe
    if _probe is None:
        _probe = Probe()
    return _probe


def record_event(t: str, d: dict) -> dict:
    p = get_probe()
    return p.record_event(t, d)


def record_error(e: Exception, ctx: dict | None = None) -> dict:
    return get_probe().record_error(e, ctx)


def record_tool_call(name: str, args: dict, result: Any, dur: float) -> dict:
    return get_probe().record_tool_call(name, args, result, dur)


def get_stats() -> dict:
    return get_probe().get_stats()


def get_summary() -> dict:
    return get_probe().get_summary()
