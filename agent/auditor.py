"""审核引擎 — 每次工具调用后自动检查，发现错误自动修复。"""
from __future__ import annotations

import json
import os
import time
import traceback
from typing import Any, Callable

from .auditor_rules import RULES, PASS, WARN, RETRY, FIX, BLOCK, AuditRule


class AuditResult:
    """一次审核的结果。"""
    __slots__ = ('status', 'rule_name', 'message', 'tool_name', 'args',
                 'duration', 'severity', 'retry_count', 'max_retries', 'ts')

    def __init__(self, status: str, rule_name: str = "", message: str = "",
                 tool_name: str = "", args: dict | None = None,
                 duration: float = 0.0, severity: str = "",
                 retry_count: int = 0, max_retries: int = 0):
        self.status = status
        self.rule_name = rule_name
        self.message = message
        self.tool_name = tool_name
        self.args = args or {}
        self.duration = duration
        self.severity = severity or status
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.ts = time.time()

    def to_dict(self) -> dict:
        return {
            "status": self.status, "rule": self.rule_name,
            "message": self.message, "tool": self.tool_name,
            "args": self.args, "duration": round(self.duration, 2),
            "severity": self.severity, "ts": self.ts,
        }

    @classmethod
    def pass_(cls, tool_name: str = "", duration: float = 0.0) -> "AuditResult":
        return cls(PASS, "", "", tool_name, duration=duration)

    @classmethod
    def warn(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
             **kw) -> "AuditResult":
        return cls(WARN, rule.name, rule.message, tool_name, duration=duration, severity=WARN, **kw)

    @classmethod
    def retry(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
              retry_count: int = 0, **kw) -> "AuditResult":
        return cls(RETRY, rule.name, rule.message, tool_name, duration=duration,
                   severity=RETRY, retry_count=retry_count, max_retries=rule.max_retries, **kw)

    @classmethod
    def fix(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
            **kw) -> "AuditResult":
        return cls(FIX, rule.name, rule.message, tool_name, duration=duration, severity=FIX, **kw)

    @classmethod
    def block(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
              **kw) -> "AuditResult":
        return cls(BLOCK, rule.name, rule.message, tool_name, duration=duration, severity=BLOCK, **kw)


class Auditor:
    """审核引擎 — 单例，规则驱动，零 LLM 调用。"""

    _instance = None
    _lock = None

    def __new__(cls):
        if cls._instance is None:
            from threading import Lock
            cls._lock = Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.records: list[AuditResult] = []
        self._retry_counts: dict[str, int] = {}
        self._on_audit: list[Callable] = []
        self.max_records = 500

    # ── 订阅 ──
    def on_audit(self, callback: Callable[[AuditResult], None]):
        self._on_audit.append(callback)

    # ── 审核一次工具调用 ──
    def audit(self, tool_name: str, args: dict,
              result: str = "", duration: float = 0.0,
              error_type: str = "") -> AuditResult:
        """对一次工具调用执行审核，返回结果。"""
        result_str = result or ""
        key = f"{tool_name}:{str(list(args.items()))[:60]}"

        for rule in RULES:
            try:
                if not rule.check(tool_name, args, result_str, duration, error_type):
                    continue
            except Exception:
                continue

            if rule.severity == BLOCK:
                r = AuditResult.block(rule, tool_name, duration)
                self._record(r)
                return r

            if rule.severity == RETRY:
                rc = self._retry_counts.get(key, 0)
                if rc < rule.max_retries:
                    self._retry_counts[key] = rc + 1
                    r = AuditResult.retry(rule, tool_name, duration, retry_count=rc)
                    self._record(r)
                    return r

            if rule.severity == FIX:
                r = AuditResult.fix(rule, tool_name, duration)
                self._record(r)
                if rule.fix == "mkdir":
                    self._apply_mkdir_fix(args)
                return r

            if rule.severity == WARN:
                r = AuditResult.warn(rule, tool_name, duration)
                self._record(r)
                return r

        # 全部通过
        r = AuditResult.pass_(tool_name, duration)
        self._record(r)
        return r

    def _apply_mkdir_fix(self, args: dict):
        """修复：自动创建父目录。"""
        fp = args.get("file_path", "")
        if not fp:
            return
        d = os.path.dirname(os.path.abspath(fp))
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass

    def _record(self, r: AuditResult):
        self.records.append(r)
        if len(self.records) > self.max_records:
            self.records.pop(0)
        for cb in self._on_audit:
            try:
                cb(r)
            except Exception:
                pass

    # ── 统计 ──
    def get_stats(self) -> dict:
        counts = {"pass": 0, "warn": 0, "retry": 0, "fix": 0, "block": 0}
        for r in self.records:
            counts[r.severity] = counts.get(r.severity, 0) + 1
        return {
            "total": len(self.records),
            "pass": counts["pass"],
            "warn": counts["warn"],
            "retry": counts["retry"],
            "fix": counts["fix"],
            "block": counts["block"],
            "health": self._health_score(counts),
        }

    @staticmethod
    def _health_score(counts: dict) -> str:
        total = sum(counts.values())
        if total == 0:
            return "excellent"
        bad = counts.get("retry", 0) + counts.get("fix", 0) + counts.get("block", 0)
        ratio = bad / total
        if ratio < 0.05:
            return "excellent"
        if ratio < 0.15:
            return "good"
        if ratio < 0.3:
            return "fair"
        return "poor"

    def get_recent(self, limit: int = 50) -> list[dict]:
        return [r.to_dict() for r in self.records[-limit:]]

    def get_report(self) -> str:
        """生成可复制的文本报告。"""
        lines = ["📋 审核报告", "═" * 50, f"总调用: {len(self.records)}"]
        s = self.get_stats()
        lines.append(f"✅ 通过: {s['pass']}  ⚠️ 警告: {s['warn']}  🔄 重试: {s['retry']}  🔧 修复: {s['fix']}  🚦 阻塞: {s['block']}")
        lines.append(f"健康状态: {s['health']}")
        lines.append("")
        lines.append("详细记录:")
        for r in self.records[-30:]:
            status_icon = {"pass": "✅", "warn": "⚠️", "retry": "🔄", "fix": "🔧", "block": "🚦"}.get(r.severity, "·")
            msg = r.message or ""
            args_preview = ""
            if r.tool_name == "bash":
                args_preview = (r.args.get("command", "") or "")[:40]
            elif r.tool_name in ("read", "write", "edit", "delete", "glob", "grep"):
                args_preview = (r.args.get("file_path", "") or r.args.get("pattern", "") or "")[:40]
            target = f" {args_preview}" if args_preview else ""
            lines.append(f"  {status_icon} {r.tool_name:8s}{target:45s} {r.duration:.2f}s")
            if msg:
                lines.append(f"     ↳ {msg}")
        return "\n".join(lines)


# ── 全局实例 ──
_auditor: Auditor | None = None


def get_auditor() -> Auditor:
    global _auditor
    if _auditor is None:
        _auditor = Auditor()
    return _auditor


def audit_tool_call(tool_name: str, args: dict,
                    result: str = "", duration: float = 0.0,
                    error_type: str = "") -> AuditResult:
    """执行审核的便捷函数。"""
    return get_auditor().audit(tool_name, args, result, duration, error_type)
