"""审核规则定义 — 纯数据，零逻辑，可扩展。"""
from __future__ import annotations

from typing import Callable

# ── 审核结果状态 ──
PASS  = "pass"   # ✅ 通过
WARN  = "warn"   # ⚠️ 警告（继续）
RETRY = "retry"  # 🔄 重试
FIX   = "fix"    # 🔧 修复（自动）
BLOCK = "block"  # 🚦 阻塞（用户介入）

# ── 规则条目 ──

class AuditRule:
    """一条审核规则。"""
    __slots__ = ('name', 'check', 'severity', 'message', 'max_retries', 'fix')

    def __init__(self, name: str, check: Callable, severity: str,
                 message: str = "", max_retries: int = 0, fix: str = ""):
        self.name = name
        self.check = check          # function(tool_name, args, result, duration, error_type) -> bool
        self.severity = severity    # pass/warn/retry/fix/block
        self.message = message
        self.max_retries = max_retries
        self.fix = fix              # fix action name


# ── 危险命令检测 ──
DANGEROUS_COMMANDS = [
    "rm -rf", "rd /s", "del /f", "format",
    "shutdown", "taskkill /f", "net user",
    "reg delete", "cipher /w",
]

# ── 所有规则 ──
RULES: list[AuditRule] = [

    # ════════════════════════════════════════════
    # 阻塞级 (BLOCK)
    # ════════════════════════════════════════════

    AuditRule("dangerous_command", lambda n, a, r, d, e:
        n == "bash" and any(cmd in (a.get("command", "") or "").lower() for cmd in DANGEROUS_COMMANDS),
        BLOCK, message="危险操作已阻止"),

    AuditRule("dangerous_delete", lambda n, a, r, d, e:
        n == "delete" and a.get("file_path", "").strip() in ("/", "D:\\", "C:\\", "C:", "D:"),
        BLOCK, message="危险删除操作已阻止"),

    AuditRule("empty_delete", lambda n, a, r, d, e:
        n == "delete" and not (a.get("file_path", "") or "").strip(),
        WARN, message="delete 未指定 file_path 参数，工具将自动报错"),

    # ════════════════════════════════════════════
    # 重试级 (RETRY)
    # ════════════════════════════════════════════

    AuditRule("empty_result", lambda n, a, r, d, e:
        n in ("bash", "web", "web_search", "glob", "grep") and not (r or "").strip(),
        RETRY, message="结果为空，自动重试", max_retries=2),

    AuditRule("timeout", lambda n, a, r, d, e:
        d > 30 and n == "bash",
        RETRY, message="命令超时，自动重试", max_retries=1),

    AuditRule("adb_not_found", lambda n, a, r, d, e:
        n == "bash" and "error" in (r or "").lower() and "adb" in (a.get("command", "") or ""),
        RETRY, message="ADB 错误，自动重试", max_retries=2),

    AuditRule("network_error", lambda n, a, r, d, e:
        n in ("web", "web_search") and any(k in (r or "").lower() for k in ("timeout", "refused", "connection")),
        RETRY, message="网络错误，自动重试", max_retries=2),

    # ════════════════════════════════════════════
    # 修复级 (FIX)
    # ════════════════════════════════════════════

    AuditRule("file_not_found", lambda n, a, r, d, e:
        n == "read" and any(k in (r or "").lower() for k in ("no such file", "找不到", "not found", "不存在")),
        FIX, message="文件不存在，尝试创建", fix="mkdir"),

    AuditRule("write_failed_dir", lambda n, a, r, d, e:
        n == "write" and any(k in (r or "").lower() for k in ("找不到路径", "no such", "系统找不到")),
        FIX, message="写入失败，检查目录", fix="mkdir"),

    AuditRule("build_failed", lambda n, a, r, d, e:
        n == "bash" and "exit code" in (r or "").lower() and any(k in (a.get("command", "") or "").lower() for k in ("build", "compile", "gradle", "mvn")),
        FIX, message="构建失败，尝试修复", fix="build_retry"),

    # ════════════════════════════════════════════
    # 警告级 (WARN)
    # ════════════════════════════════════════════

    AuditRule("grep_no_match", lambda n, a, r, d, e:
        n == "grep" and not (r or "").strip(),
        WARN, message="搜索无匹配"),

    AuditRule("slow_call", lambda n, a, r, d, e:
        d > 10,
        WARN, message="执行较慢 (>10s)"),

    AuditRule("error_in_output", lambda n, a, r, d, e:
        bool(e) or (n != "read" and any(k in (r or "")[:200].lower() for k in ("error", "❌", "失败", "exception", "traceback"))),
        WARN, message="检测到错误信息"),
]
