"""审核引擎 v2 — 详细链路追踪，每次审计输出完整决策上下文。"""
from __future__ import annotations

import json
import os
import time
import traceback
from typing import Any, Callable

from .auditor_rules import RULES, PASS, WARN, RETRY, FIX, BLOCK, AuditRule


class AuditDetail:
    """一次审核的详细决策记录。"""
    __slots__ = ('rule', 'trigger', 'analysis', 'strategy', 'before', 'after',
                 'before_preview', 'after_preview')

    def __init__(self, rule: str, trigger: str, analysis: str, strategy: str,
                 before: str = "", after: str = "",
                 before_preview: str = "", after_preview: str = ""):
        self.rule = rule
        self.trigger = trigger
        self.analysis = analysis
        self.strategy = strategy
        self.before = before
        self.after = after
        self.before_preview = before_preview[:200]
        self.after_preview = after_preview[:200]

    def to_dict(self) -> dict:
        return {
            "rule": self.rule, "trigger": self.trigger,
            "analysis": self.analysis, "strategy": self.strategy,
            "before": self.before_preview, "after": self.after_preview,
        }


class AuditResult:
    """一次审核的结果（v2：含完整决策链路）。"""
    __slots__ = ('status', 'rule_name', 'message', 'tool_name', 'args',
                 'duration', 'severity', 'retry_count', 'max_retries',
                 'ts', 'detail', 'result_snippet')

    def __init__(self, status: str, rule_name: str = "", message: str = "",
                 tool_name: str = "", args: dict | None = None,
                 duration: float = 0.0, severity: str = "",
                 retry_count: int = 0, max_retries: int = 0,
                 detail: AuditDetail | None = None,
                 result_snippet: str = ""):
        self.status = status
        self.rule_name = rule_name
        self.message = message
        self.tool_name = tool_name
        self.args = args or {}
        self.duration = duration
        self.severity = severity or status
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.detail = detail
        self.result_snippet = result_snippet[:300]
        self.ts = time.time()

    def to_dict(self) -> dict:
        d = {
            "status": self.status, "rule": self.rule_name,
            "message": self.message, "tool": self.tool_name,
            "args": self.args, "duration": round(self.duration, 2),
            "severity": self.severity, "ts": self.ts,
            "result": self.result_snippet,
        }
        if self.detail:
            d["detail"] = self.detail.to_dict()
        return d

    @classmethod
    def pass_(cls, tool_name: str = "", duration: float = 0.0,
              result_snippet: str = "") -> "AuditResult":
        return cls(PASS, "", "", tool_name, duration=duration, result_snippet=result_snippet)

    @classmethod
    def warn(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
             detail: AuditDetail | None = None, result_snippet: str = "") -> "AuditResult":
        return cls(WARN, rule.name, rule.message, tool_name, duration=duration,
                   severity=WARN, detail=detail, result_snippet=result_snippet)

    @classmethod
    def retry(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
              retry_count: int = 0, detail: AuditDetail | None = None,
              result_snippet: str = "") -> "AuditResult":
        return cls(RETRY, rule.name, rule.message, tool_name, duration=duration,
                   severity=RETRY, retry_count=retry_count, max_retries=rule.max_retries,
                   detail=detail, result_snippet=result_snippet)

    @classmethod
    def fix(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
            detail: AuditDetail | None = None, result_snippet: str = "") -> "AuditResult":
        return cls(FIX, rule.name, rule.message, tool_name, duration=duration,
                   severity=FIX, detail=detail, result_snippet=result_snippet)

    @classmethod
    def block(cls, rule: AuditRule, tool_name: str = "", duration: float = 0.0,
              detail: AuditDetail | None = None, result_snippet: str = "") -> "AuditResult":
        return cls(BLOCK, rule.name, rule.message, tool_name, duration=duration,
                   severity=BLOCK, detail=detail, result_snippet=result_snippet)


class Auditor:
    """审核引擎 v2 — 详细链路追踪。"""

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

    def on_audit(self, callback: Callable[[AuditResult], None]):
        self._on_audit.append(callback)

    def audit(self, tool_name: str, args: dict,
              result: str = "", duration: float = 0.0,
              error_type: str = "") -> AuditResult:
        """执行审核，返回含完整决策链路的结果。"""
        result_str = result or ""
        key = f"{tool_name}:{str(list(args.items()))[:60]}"
        snippet = result_str[:300]

        for rule in RULES:
            try:
                if not rule.check(tool_name, args, result_str, duration, error_type):
                    continue
            except Exception:
                continue

            # 提取触发详情和修复策略
            trigger = self._build_trigger(rule, tool_name, args, result_str, error_type)
            analysis = rule.message or "规则触发"
            strategy = self._build_strategy(rule, tool_name, args)

            if rule.severity == BLOCK:
                detail = AuditDetail(rule.name, trigger, analysis, strategy,
                                     before=result_str[:200],
                                     before_preview=trigger)
                r = AuditResult.block(rule, tool_name, duration, detail=detail, result_snippet=snippet)
                self._record(r)
                return r

            if rule.severity == RETRY:
                rc = self._retry_counts.get(key, 0)
                if rc < rule.max_retries:
                    self._retry_counts[key] = rc + 1
                    strategy = f"第 {rc+1}/{rule.max_retries} 次重试: {strategy}"
                    detail = AuditDetail(rule.name, trigger, analysis, strategy,
                                         before=result_str[:200],
                                         before_preview=f"原结果: {result_str[:100]}")
                    r = AuditResult.retry(rule, tool_name, duration, retry_count=rc,
                                          detail=detail, result_snippet=snippet)
                    self._record(r)
                    return r

            if rule.severity == FIX:
                before_state = ""
                after_state = ""
                if rule.fix == "mkdir":
                    fp = args.get("file_path", "")
                    before_state = f"文件不存在: {fp}" if fp else trigger
                    d = os.path.dirname(os.path.abspath(fp)) if fp else ""
                    try:
                        os.makedirs(d, exist_ok=True)
                        after_state = f"目录已创建: {d}" if d else "已修复"
                    except Exception as ex:
                        after_state = f"目录创建失败: {ex}"

                detail = AuditDetail(rule.name, trigger, analysis, strategy,
                                     before=before_state, after=after_state,
                                     before_preview=before_state, after_preview=after_state)
                r = AuditResult.fix(rule, tool_name, duration, detail=detail, result_snippet=snippet)
                self._record(r)
                return r

            if rule.severity == WARN:
                detail = AuditDetail(rule.name, trigger, analysis, strategy,
                                     before=result_str[:200],
                                     before_preview=result_str[:100])
                r = AuditResult.warn(rule, tool_name, duration, detail=detail, result_snippet=snippet)
                self._record(r)
                return r

        r = AuditResult.pass_(tool_name, duration, result_snippet=snippet)
        self._record(r)
        return r

    def _build_trigger(self, rule: AuditRule, tool: str, args: dict,
                       result: str, error_type: str) -> str:
        """生成人类可读的触发原因。"""
        if tool == "bash":
            cmd = (args.get("command", "") or "")[:80]
            if any(k in result.lower()[:100] for k in ("error", "❌", "exception", "traceback")):
                return f"命令 `{cmd}` 输出包含错误信息"
            if "exit code" in result.lower():
                lines = [l for l in result.split("\n") if "exit code" in l.lower() or "error" in l.lower()]
                return f"命令 `{cmd}` 退出码异常: {(lines[0] if lines else result)[:120]}"
            return f"命令触发: {cmd}"
        if tool in ("read", "write", "edit", "delete"):
            fp = args.get("file_path", "")[:60]
            if not fp and tool == "delete":
                return f"危险删除操作: 未指定文件路径"
            if not fp:
                return f"文件操作: 路径为空"
            if "not found" in result.lower() or "找不到" in result:
                return f"文件不存在: {fp}"
            if "permission" in result.lower():
                return f"权限不足: {fp}"
            return f"文件操作: {fp}"
        if tool == "grep":
            pat = args.get("pattern", "")[:40]
            return f"搜索 `{pat}` 无匹配结果"
        if error_type:
            return f"错误类型: {error_type}"
        return f"工具 `{tool}` 结果异常"

    def _build_strategy(self, rule: AuditRule, tool: str, args: dict) -> str:
        """生成修复策略描述。"""
        strategies = {
            "dangerous_command": f"检测到危险命令 `{(args.get('command','') or '')[:40]}`，已阻止执行",
            "dangerous_delete": "检测到危险删除操作 (路径: " + str(args.get('file_path', '') or '空')[:30] + ")，已阻止",
            "empty_result": f"检查 {tool} 参数后重新执行",
            "timeout": "终止当前命令，降低复杂度后重试",
            "adb_not_found": "检查 ADB 连接状态后重试",
            "network_error": "等待 3 秒后重新请求",
            "file_not_found": f"自动创建父目录后重新读取",
            "write_failed_dir": "检查并创建目标目录后重新写入",
            "build_failed": "清理缓存后重新构建",
            "grep_no_match": "搜索结果为空，属于正常情况，继续执行",
            "slow_call": f"`{tool}` 执行耗时较长，已记录",
            "error_in_output": "检测到错误输出但未阻断，标记警告",
        }
        return strategies.get(rule.name, f"执行修复策略: {rule.name}")

    def _record(self, r: AuditResult):
        self.records.append(r)
        if len(self.records) > self.max_records:
            self.records.pop(0)
        for cb in self._on_audit:
            try:
                cb(r)
            except Exception:
                pass

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
        lines = []
        lines.append("📋 审核报告")
        lines.append("═" * 60)
        s = self.get_stats()
        lines.append(f"总调用: {s['total']}  |  健康状态: {s['health']}")
        lines.append(f"✅ 通过: {s['pass']}  ⚠️ 警告: {s['warn']}  🔄 重试: {s['retry']}")
        lines.append(f"🔧 修复: {s['fix']}  🚦 阻塞: {s['block']}")
        lines.append("")
        lines.append("详细链路记录:")
        lines.append("─" * 60)
        for r in self.records[-20:]:
            icon = {"pass": "✅", "warn": "⚠️", "retry": "🔄", "fix": "🔧", "block": "🚦"}.get(r.severity, "·")
            cmd = ""
            if r.tool_name == "bash":
                cmd = (r.args.get("command", "") or "")[:50]
            elif r.tool_name in ("read", "write", "edit"):
                cmd = (r.args.get("file_path", "") or "")[:50]
            elif r.tool_name in ("grep", "glob"):
                cmd = (r.args.get("pattern", "") or "")[:50]
            lines.append(f"{icon} {r.tool_name:8s} {cmd:50s} {r.duration:.2f}s")
            if r.detail:
                d = r.detail
                lines.append(f"   └─ 触发: {d.trigger[:70]}")
                if d.strategy:
                    lines.append(f"   └─ 策略: {d.strategy[:70]}")
                if d.before_preview:
                    lines.append(f"   └─ 修复前: {d.before_preview[:70]}")
                if d.after_preview:
                    lines.append(f"   └─ 修复后: {d.after_preview[:70]}")
            lines.append("")
        return "\n".join(lines)


_auditor: Auditor | None = None


def get_auditor() -> Auditor:
    global _auditor
    if _auditor is None:
        _auditor = Auditor()
    return _auditor


def audit_tool_call(tool_name: str, args: dict,
                    result: str = "", duration: float = 0.0,
                    error_type: str = "") -> AuditResult:
    return get_auditor().audit(tool_name, args, result, duration, error_type)
