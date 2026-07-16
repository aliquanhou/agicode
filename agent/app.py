"""AgiCode Web — 网页版入口，通过 FastAPI + Monaco Editor 提供全功能 GUI。

启动流程：
  1. 创建 Agent 实例
  2. 启动 FastAPI 本地服务器 (随机端口)
  3. 订阅 Agent 事件到 SSE
  4. 自动打开浏览器
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from typing import Any

import customtkinter as ctk

from .core import Agent, StreamHandler
from .prompt import SYSTEM_PROMPT
from .providers import (
    AnthropicProvider,
    OpenAIProvider,
)
from .scheduler import get_scheduler
from .watcher import get_watcher
from .transcript import Transcript
from .workflow import Workflow
from .app_dialogs import CodeReviewDialog, ResearchDialog, SchedulerDialog, WatcherDialog
from .web_server import WebServer


# ── Color / style ──

COLOR_USER = "#4CAF50"
COLOR_ASSISTANT = "#E0E0E0"
COLOR_TOOL_RESULT = "#FFB74D"

FONT_FAMILY = "Microsoft YaHei"
FONT_MONO = "Consolas"

TOOL_ICONS = {
    "read": "📖", "write": "✏️", "edit": "🔧",
    "glob": "🔍", "grep": "🔎", "bash": "💻", "think": "🧠",
    "system_info": "🖥️", "process": "⚙️", "web": "🌐", "screencap": "📸",
    "browser": "🌍", "background": "⏳", "plan": "📋", "task": "✅",
    "ast": "🌳", "dep_graph": "🕸", "call_chain": "🔗",
}

PROVIDER_PRESETS = {
    "DeepSeek": {"base_url": "https://api.deepseek.com"},
    "Anthropic Claude": {"base_url": ""},
    "OpenAI": {"base_url": "https://api.openai.com/v1"},
}

PROVIDER_NAMES = list(PROVIDER_PRESETS.keys())


def _get_default_provider() -> str:
    return PROVIDER_NAMES[0] if PROVIDER_NAMES else "OpenAI"


def _get_provider(provider_name: str, api_key: str, model: str, base_url: str | None = None) -> OpenAIProvider | AnthropicProvider:
    if provider_name == "Anthropic Claude":
        return AnthropicProvider({
            "api_key": api_key, "model": model or "claude-sonnet-4-20250514", "base_url": base_url or "",
        })
    else:
        return OpenAIProvider({
            "api_key": api_key, "model": model or "gpt-4o",
            "base_url": base_url or PROVIDER_PRESETS.get(provider_name, {}).get("base_url", ""),
        })


get_default_provider = _get_default_provider
get_provider = _get_provider


# ── Web Stream Handler ──

class WebStreamHandler(StreamHandler):
    """StreamHandler 桥接：将 Agent 事件推送到 web_server SSE 和内部队列。"""

    def __init__(self, msg_queue: queue.Queue, web_server: WebServer | None = None):
        self.queue = msg_queue
        self.web_server = web_server

    def on_text(self, text: str) -> None:
        self.queue.put(("text", text))
        if self.web_server:
            self.web_server.push_sse("text", {"delta": text})

    def on_thinking(self, text: str) -> None:
        self.queue.put(("thinking", text))
        if self.web_server:
            self.web_server.push_sse("thought", {"delta": text})

    def on_tool_start(self, name: str, input_data: dict) -> None:
        self.queue.put(("tool_start", (name, input_data)))
        if self.web_server:
            self.web_server.push_sse("tool", {"subtype": "start", "tool_name": name})

    def on_tool_result(self, result: str) -> None:
        self.queue.put(("tool_result", result))
        if self.web_server:
            self.web_server.push_sse("tool", {"subtype": "result", "tool_name": "", "result": result[:2000]})

    def on_tool_output(self, text: str) -> None:
        if not text:
            self.queue.put(("heartbeat", None))
            return
        self.queue.put(("tool_output", text))

    def on_error(self, error: str) -> None:
        self.queue.put(("error", error))
        if self.web_server:
            self.web_server.push_sse("error", {"message": error})

    def on_turn_end(self) -> None:
        self.queue.put(("turn_end", None))

    def on_turn_plan(self, tool_count: int) -> None:
        self.queue.put(("turn_plan", tool_count))

    def on_complete(self) -> None:
        self.queue.put(("complete", None))
        if self.web_server:
            self.web_server.push_sse("session", {"subtype": "end"})


# ── Main Application ──

class AgentApp(ctk.CTk):
    """AgiCode Web 入口 —— 隐藏在系统托盘的 tkinter 窗口。"""

    def __init__(self):
        super().__init__()
        self.title("AgiCode")
        self.geometry("1x1")  # 极小窗口，用户看不到
        self.withdraw()  # 隐藏窗口

        # State
        self.agent: Agent | None = None
        self.provider_name: str = get_default_provider()
        self.api_key: str = ""
        self.model: str = ""
        self.base_url: str = ""
        self.system_prompt: str = SYSTEM_PROMPT
        self.busy = False
        self.ui_queue: queue.Queue = queue.Queue()

        # 透明工作流
        self.transcript: Transcript | None = None
        self.workflow: Workflow | None = None
        self._mcp_servers: list = []

        # Tool tracking (供 REST API /api/tools 查询)
        self.tool_status: dict[str, str] = {t: "idle" for t in TOOL_ICONS}
        self._active_tool: str | None = None
        self._active_tool_start: float = 0.0
        self._last_input: str = ""
        self._think_start_time: float = 0.0

        # ── 启动 Web 服务器 ──
        self.web_server = WebServer(agent_app=self)
        port = self.web_server.start()
        url = self.web_server.get_url()

        # ── 加载配置 ──
        self._load_config()

        # ── 启动队列轮询（维持 tool_status 等内部状态）──
        self._poll_queue()

        # ── 打开浏览器 ──
        print(f"\n  AgiCode Web 已启动: {url}")
        print(f"  按 Ctrl+C 退出\n")
        webbrowser.open(url)

    def _config_path(self):
        return os.path.join(os.path.dirname(__file__), "..", "config.json")

    def _load_config(self):
        p = self._config_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self.provider_name = d.get("provider", get_default_provider())
                self.api_key = d.get("api_key", "")
                self.model = d.get("model", "")
                self.base_url = d.get("base_url", "")
                self._mcp_servers = d.get("mcp_servers", [])
                self._init_agent()
            except Exception:
                pass

    def _save_config(self):
        """保存配置到 config.json"""
        try:
            p = self._config_path()
            with open(p, "w", encoding="utf-8") as f:
                json.dump({
                    "provider": self.provider_name,
                    "api_key": self.api_key,
                    "model": self.model,
                    "base_url": self.base_url,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _init_agent(self):
        if not self.api_key:
            return
        try:
            self.transcript = Transcript(agent_id="agicode-web")
            # WebStreamHandler 已推送 SSE，这里不再重复订阅

            config = {
                "api_key": self.api_key,
                "model": self.model,
                "base_url": self.base_url,
                "max_tokens": 8192,
                "temperature": 0.0,
                "request_timeout": 120,
                "enable_speculative": True,
                "enable_streaming_parser": True,
                "mcp_servers": getattr(self, '_mcp_servers', []),
            }
            self.agent = Agent(config=config, transcript=self.transcript)
            self.workflow = self.agent.workflow
        except Exception as e:
            print(f"[AgiCode] 初始化失败: {e}")

    # ── 发送消息 ──

    def _send_text(self, text: str):
        if self.busy:
            return
        if not self.api_key:
            self.web_server.push_sse("error", {"message": "请先配置 API Key"})
            return
        if not self.agent:
            self._init_agent()
            if not self.agent:
                self.web_server.push_sse("error", {"message": "初始化失败"})
                return

        self._last_input = text
        self.busy = True
        self._think_start_time = time.time()

        # 重置工具状态
        for t in self.tool_status:
            self._set_tool_status(t, "idle")

        t = threading.Thread(target=self._run_thread, args=(text,), daemon=True)
        t.start()

    def _run_thread(self, text: str):
        try:
            h = WebStreamHandler(self.ui_queue, web_server=self.web_server)
            self.agent.run_iteration(text, h)
        except Exception as e:
            self.web_server.push_sse("error", {"message": str(e)})
            self.web_server.push_sse("session", {"subtype": "end"})

    def _stop_agent(self):
        if not self.busy:
            return
        self._force_reset("⏹ 用户手动终止")

    def _retry_last(self):
        if self.busy or not self._last_input:
            return
        self._send_text(self._last_input)

    def _clear_chat(self):
        self.busy = False
        if self.agent:
            self.agent.messages = []
        for t in self.tool_status:
            self._set_tool_status(t, "idle")

    def _force_reset(self, reason: str = ""):
        self.busy = False
        if self.agent:
            try:
                from .context import sanitize_messages
                self.agent.messages = sanitize_messages(self.agent.messages)
            except Exception:
                pass
        self.web_server.push_sse("session", {"subtype": "end"})
        if reason:
            self.web_server.push_sse("error", {"message": reason})

    # ── 工具面板状态 ──

    def _set_tool_status(self, name: str, status: str):
        self.tool_status[name] = status

    def _on_complete(self):
        self.busy = False
        if self._think_start_time > 0:
            elapsed = time.time() - self._think_start_time
            if elapsed >= 0.5:
                unit = "s" if elapsed < 60 else "m"
                val = elapsed if elapsed < 60 else elapsed / 60
                self.web_server.push_sse("text", {"delta": f"\n  🧠 思考 {val:.1f}{unit}\n"})
        self._think_start_time = 0.0

    # ── 队列轮询（维持内部状态同步）──

    def _poll_queue(self):
        """轮询队列更新工具面板状态。"""
        processed = 0
        try:
            while True:
                if processed >= 200:
                    self.update_idletasks()
                    self.after(1, self._poll_queue)
                    return
                t, d = self.ui_queue.get_nowait()
                self._handle_msg(t, d)
                processed += 1
        except queue.Empty:
            pass
        self.after(250, self._poll_queue)

    def _handle_msg(self, t: str, d: Any):
        if t == "tool_start":
            name, inp = d
            if self._active_tool == name:
                pass
            else:
                if self._active_tool:
                    self._set_tool_status(self._active_tool, "done")
                self._active_tool = name
                self._active_tool_start = time.time()
                self._set_tool_status(name, "running")
        elif t == "tool_result":
            import re
            is_err = any(kw in d[:100].lower() for kw in ("错误", "error", "失败", "❌"))
            if self._active_tool:
                self._set_tool_status(self._active_tool, "error" if is_err else "done")
                self._active_tool = None
        elif t == "error":
            if self._active_tool:
                self._set_tool_status(self._active_tool, "error")
                self._active_tool = None
        elif t == "complete":
            self._on_complete()
        elif t == "turn_plan":
            pass  # 工作流状态由 transcript → SSE 处理

    # ── 启动 ──

    def run(self):
        self.mainloop()


def run():
    app = AgentApp()
    app.run()
