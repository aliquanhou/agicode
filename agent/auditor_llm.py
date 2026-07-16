"""LLM 审核子代理 — 语义级代码/任务质量审计。

只对 write/edit/plan/复杂 bash 触发，规则引擎通过后由 LLM
做深层语义检查：代码逻辑、安全漏洞、性能问题。
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import traceback
from typing import Any, Callable

from .auditor import AuditDetail, AuditResult, FIX, WARN, BLOCK

# ── 哪些工具需要 LLM 审核 ──
LLM_AUDIT_TOOLS = {"write", "edit", "plan", "task", "bash", "replace"}

# ── 跳过 LLM 审核的简单命令模式 ──
SKIP_BASH_PATTERNS = [
    r"^(ls|dir|echo|cd |pwd|whoami|hostname|date|time)\b",
    r"^(git status|git log|git diff|git branch)",
    r"curl.*-s.*api/health",
    r"^(pip|npm|npx) (list|--version|-v)",
    r"^(cat|head|tail|wc|sort|uniq)\b",
    r"^(python3?|node) --version",
    r"^(which|where|type)\b",
    r"^#",
]

# ── LLM 审核系统提示词（轻量级） ──
AUDITOR_SYSTEM_PROMPT = """你是 AgiCode 的代码审核子代理。你的任务是审核主 Agent 的工具调用结果，发现潜在问题。

## 审核范围
- **write/edit**: 检查写入的代码是否有语法错误、逻辑错误、安全漏洞
- **plan/task**: 检查计划的步骤是否完整、合理
- **bash**: 检查命令是否安全、参数是否正确

## 输出格式
以 JSON 返回审核结果，不要添加其他内容：
```json
{
  "decision": "pass|warn|block",
  "confidence": 0.0-1.0,
  "issues": [
    {
      "severity": "error|warning|info",
      "description": "问题描述",
      "suggestion": "修复建议"
    }
  ],
  "summary": "一句话审核结论"
}
```

## 规则
1. pass = 没有问题，继续执行
2. warn = 有小问题但不影响，标记警告
3. block = 严重问题，建议阻止
4. 如果没有发现问题，必须返回 pass
5. 不要过度审核——只关注真正的问题
"""


def _should_skip_llm_audit(tool_name: str, args: dict, result: str) -> bool:
    """判断是否跳过 LLM 审核（简单操作不审）。"""
    if tool_name not in LLM_AUDIT_TOOLS:
        return True

    # bash：只审复杂命令
    if tool_name == "bash":
        cmd = (args.get("command", "") or "").strip()
        for pat in SKIP_BASH_PATTERNS:
            if re.match(pat, cmd, re.IGNORECASE):
                return True
        # 短命令跳过
        if len(cmd) < 30:
            return True

    # 结果为空的不审
    if not result or len(result.strip()) < 10:
        return True

    return False


def _build_audit_prompt(tool_name: str, args: dict, result: str) -> str:
    """构建审核提示词。"""
    cmd_or_path = ""
    content = ""

    if tool_name == "write":
        path = args.get("file_path", "")
        content = args.get("content", "")[:2000]
        cmd_or_path = f"文件路径: {path}"
        if content:
            cmd_or_path += f"\n\n写入内容 ({len(content)} 字符):\n```\n{content}\n```"

    elif tool_name == "edit":
        path = args.get("file_path", "")
        old = args.get("old_text", "")[:500]
        new = args.get("new_text", "")[:500]
        cmd_or_path = f"文件路径: {path}\n\n替换前:\n```\n{old}\n```\n\n替换后:\n```\n{new}\n```"

    elif tool_name in ("plan", "task"):
        action = args.get("action", "")
        title = args.get("title", "")
        steps = args.get("steps", [])
        cmd_or_path = f"操作: {action}\n标题: {title}\n步骤: {json.dumps(steps, ensure_ascii=False)[:1000]}"

    elif tool_name == "bash":
        cmd = args.get("command", "")[:500]
        cmd_or_path = f"命令: {cmd}"

    elif tool_name == "replace":
        path = args.get("file_path", "")
        old = args.get("old", "")[:500]
        new = args.get("new", "")[:500]
        cmd_or_path = f"文件路径: {path}\n\n替换前:\n```\n{old}\n```\n\n替换后:\n```\n{new}\n```"

    result_preview = result[:2000] if result else "(空)"

    return f"""## 工具调用
工具: {tool_name}
{cmd_or_path}

## 执行结果
```
{result_preview}
```

请审核这次调用的结果，按要求的 JSON 格式输出。"""


class LlmAuditor:
    """LLM 审核子代理。"""

    def __init__(self):
        self._thread = None
        self._results: dict[str, dict] = {}
        self._results_lock = threading.Lock()
        self._on_result: list[Callable] = []
        self._provider = None
        self._total_calls = 0
        self._slow_calls = 0

    def on_result(self, callback: Callable[[str, dict], None]):
        self._on_result.append(callback)

    def audit_async(self, key: str, tool_name: str, args: dict,
                    result: str, duration: float):
        """异步执行 LLM 审核（不阻塞主流程）。"""
        if _should_skip_llm_audit(tool_name, args, result):
            return

        # 记录开始时间
        t0 = time.time()

        def _run():
            try:
                llm_result = self._audit_sync(tool_name, args, result)
                elapsed = time.time() - t0
                llm_result["llm_duration"] = round(elapsed, 2)

                self._total_calls += 1
                if elapsed > 5:
                    self._slow_calls += 1

                with self._results_lock:
                    self._results[key] = llm_result

                for cb in self._on_result:
                    try:
                        cb(key, llm_result)
                    except Exception:
                        pass
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True, name=f"llm-audit-{tool_name}").start()

    def _audit_sync(self, tool_name: str, args: dict, result: str) -> dict:
        """同步执行 LLM 审核。"""
        prompt = _build_audit_prompt(tool_name, args, result)

        # 使用本地 Provider 调用
        try:
            response = self._llm_call(prompt)
            return self._parse_response(response, tool_name)
        except Exception:
            return {"decision": "pass", "confidence": 0.0,
                    "issues": [], "summary": "LLM 审核调用失败，自动放行"}

    def _llm_call(self, prompt: str) -> str:
        """调用 LLM。"""
        # 尝试用配置的 provider
        try:
            if self._provider is None:
                from .providers import create_llm_provider
                api_key = (os.environ.get("ANTHROPIC_API_KEY") or
                           os.environ.get("DEEPSEEK_API_KEY") or
                           os.environ.get("OPENAI_API_KEY") or "")
                if not api_key:
                    return ""
                model = os.environ.get("AUDITOR_MODEL", "deepseek-chat")
                self._provider = create_llm_provider({
                    "api_key": api_key,
                    "model": model,
                    "temperature": 0.0,
                    "max_tokens": 1024,
                })

            result = self._provider.complete(
                system=AUDITOR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.0,
            )
            return result.get("content", "")
        except ImportError:
            return ""
        except Exception:
            return ""

    def _parse_response(self, response: str, tool_name: str) -> dict:
        """解析 LLM 返回的 JSON。"""
        if not response:
            return {"decision": "pass", "confidence": 0.0,
                    "issues": [], "summary": "LLM 无返回，自动放行"}

        # 提取 JSON
        try:
            # 查找 ```json ... ``` 块
            m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
            if m:
                json_str = m.group(1)
            else:
                # 直接尝试解析整个响应
                json_str = response

            data = json.loads(json_str)
            decision = data.get("decision", "pass")
            if decision not in ("pass", "warn", "block"):
                decision = "pass"

            return {
                "decision": decision,
                "confidence": data.get("confidence", 0.5),
                "issues": data.get("issues", []),
                "summary": data.get("summary", ""),
            }
        except (json.JSONDecodeError, AttributeError):
            # 解析失败，尝试提取关键词
            resp_lower = response.lower()
            if "block" in resp_lower and "pass" not in resp_lower:
                return {"decision": "block", "confidence": 0.3,
                        "issues": [{"severity": "warning", "description": "LLM 审核解析失败但检测到 block 信号"}],
                        "summary": "LLM 检测到问题建议阻止"}
            return {"decision": "pass", "confidence": 0.3,
                    "issues": [], "summary": "LLM 响应解析失败，自动放行"}

    def get_stats(self) -> dict:
        return {
            "total_calls": self._total_calls,
            "slow_calls": self._slow_calls,
        }


# ── 全局实例 ──
_llm_auditor: LlmAuditor | None = None


def get_llm_auditor() -> LlmAuditor:
    global _llm_auditor
    if _llm_auditor is None:
        _llm_auditor = LlmAuditor()
    return _llm_auditor


def audit_llm_async(key: str, tool_name: str, args: dict,
                    result: str, duration: float):
    """便捷函数：异步触发 LLM 审核。"""
    get_llm_auditor().audit_async(key, tool_name, args, result, duration)
