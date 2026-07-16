"""GUI application for the Multi-LLM Agent with tool panel."""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import tkinter as tk
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
from .monaco_widget import MonacoChatWidget


# ── Color / style ──

COLOR_USER = "#4CAF50"
COLOR_ASSISTANT = "#E0E0E0"
COLOR_THINKING = "#888888"
COLOR_TOOL_NAME = "#FF9800"
COLOR_TOOL_RESULT = "#FFB74D"
COLOR_TOOL_IDLE = "#555555"
COLOR_TOOL_RUNNING = "#FFC107"
COLOR_TOOL_DONE = "#4CAF50"
COLOR_TOOL_ERROR = "#F44336"
COLOR_ERROR = "#F44336"
COLOR_SYSTEM = "#64B5F6"
COLOR_SEPARATOR = "#333333"

FONT_FAMILY = "Microsoft YaHei"
FONT_MONO = "Consolas"

TOOL_ICONS = {
    "read": "📖", "write": "✏️", "edit": "🔧",
    "glob": "🔍", "grep": "🔎", "bash": "💻", "think": "🧠",
    "system_info": "🖥️", "process": "⚙️", "web": "🌐", "screencap": "📸",
    "browser": "🌍", "background": "⏳", "plan": "📋", "task": "✅",
    "ast": "🌳", "dep_graph": "🕸", "call_chain": "🔗",
}

TOOL_CATEGORIES = [
    ("📂 文件系统", ["read", "write", "edit", "glob", "grep"]),
    ("⚡ 命令执行", ["bash", "background"]),
    ("🖥️ 系统控制", ["system_info", "process"]),
    ("🧠 智能与网络", ["think", "web", "screencap"]),
    ("🌍 浏览器", ["browser"]),
    ("🔬 代码分析", ["ast", "dep_graph", "call_chain"]),
    ("📋 工具链", ["plan", "task"]),
]

TOOL_DESCRIPTIONS = {
    "read": "读取文件", "write": "写入文件", "edit": "编辑文件",
    "glob": "搜索路径", "grep": "搜索内容", "bash": "执行命令",
    "think": "内部推理", "system_info": "系统信息",
    "process": "进程管理", "web": "网络请求", "screencap": "屏幕截图",
    "browser": "浏览器控制", "background": "后台任务",
    "ast": "AST结构分析", "dep_graph": "依赖图分析",
    "call_chain": "调用链追踪",
    "plan": "计划管理", "task": "任务状态",
}

CATEGORY_COLORS = {
    "📂 文件系统": "#42A5F5",
    "⚡ 命令执行": "#EF5350",
    "🖥️ 系统控制": "#AB47BC",
    "🧠 智能与网络": "#FFA726",
    "🌍 浏览器": "#26C6DA",
    "🔬 代码分析": "#FF7043",
    "📋 工具链": "#66BB6A",
}

PROVIDER_PRESETS = {
    "DeepSeek": {"base_url": "https://api.deepseek.com"},
    "Anthropic Claude": {"base_url": ""},
    "OpenAI": {"base_url": "https://api.openai.com/v1"},
}

PROVIDER_NAMES = list(PROVIDER_PRESETS.keys())

# ── v1.0 兼容：get_default_provider / get_provider 内联 ──

def _get_default_provider() -> str:
    return PROVIDER_NAMES[0] if PROVIDER_NAMES else "OpenAI"

def _get_provider(provider_name: str, api_key: str, model: str, base_url: str | None = None) -> OpenAIProvider | AnthropicProvider:
    if provider_name == "Anthropic Claude":
        return AnthropicProvider({
            "api_key": api_key,
            "model": model or "claude-sonnet-4-20250514",
            "base_url": base_url or "",
        })
    else:
        return OpenAIProvider({
            "api_key": api_key,
            "model": model or "gpt-4o",
            "base_url": base_url or PROVIDER_PRESETS.get(provider_name, {}).get("base_url", ""),
        })

get_default_provider = _get_default_provider
get_provider = _get_provider


# ── UI Stream Handler ──

class UIStreamHandler(StreamHandler):
    def __init__(self, msg_queue: queue.Queue):
        self.queue = msg_queue

    def on_text(self, text: str) -> None:
        self.queue.put(("text", text))

    def on_thinking(self, text: str) -> None:
        self.queue.put(("thinking", text))

    def on_tool_start(self, name: str, input_data: dict) -> None:
        self.queue.put(("tool_start", (name, input_data)))

    def on_tool_result(self, result: str) -> None:
        self.queue.put(("tool_result", result))

    def on_tool_output(self, text: str) -> None:
        # Empty string = heartbeat signal (update watchdog timer but don't display)
        if not text:
            self.queue.put(("heartbeat", None))
            return
        self.queue.put(("tool_output", text))

    def on_error(self, error: str) -> None:
        self.queue.put(("error", error))

    def on_turn_end(self) -> None:
        self.queue.put(("turn_end", None))

    def on_turn_plan(self, tool_count: int) -> None:
        self.queue.put(("turn_plan", tool_count))

    def on_complete(self) -> None:
        self.queue.put(("complete", None))


# ── Settings Dialog ──

class SettingsDialog(ctk.CTkToplevel):
    def __init__(
        self, parent: ctk.CTk,
        provider_name: str = "", api_key: str = "",
        model: str = "", base_url: str = "",
        system_prompt: str = "",
    ):
        super().__init__(parent)
        self.title("设置")
        self.geometry("640x620")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: dict | None = None

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - 640) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 620) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(f, text="LLM 提供商", font=(FONT_FAMILY, 14, "bold")).pack(anchor="w", pady=(0, 4))
        self.provider_var = ctk.StringVar(value=provider_name or get_default_provider())
        ctk.CTkOptionMenu(f, variable=self.provider_var, values=PROVIDER_NAMES,
                          font=(FONT_FAMILY, 13), dropdown_font=(FONT_FAMILY, 13), height=35,
                          command=self._on_provider_change).pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(f, text="API 密钥", font=(FONT_FAMILY, 14, "bold")).pack(anchor="w", pady=(0, 4))
        self.api_key_var = ctk.StringVar(value=api_key)
        ctk.CTkEntry(f, textvariable=self.api_key_var, show="•",
                     font=(FONT_MONO, 13), height=35).pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(f, text="API 地址（OpenAI 兼容接口）", font=(FONT_FAMILY, 14, "bold")).pack(anchor="w", pady=(0, 4))
        self.base_url_var = ctk.StringVar(value=base_url)
        ctk.CTkEntry(f, textvariable=self.base_url_var, font=(FONT_MONO, 13), height=35,
                     placeholder_text="https://api.deepseek.com").pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(f, text="模型", font=(FONT_FAMILY, 14, "bold")).pack(anchor="w", pady=(0, 4))
        self.model_var = ctk.StringVar(value=model)
        self.model_menu = ctk.CTkOptionMenu(f, variable=self.model_var,
                                            values=self._models(), font=(FONT_MONO, 13),
                                            dropdown_font=(FONT_MONO, 13), height=35)
        self.model_menu.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(f, text="系统提示词", font=(FONT_FAMILY, 14, "bold")).pack(anchor="w", pady=(0, 4))
        self.prompt_text = ctk.CTkTextbox(f, font=(FONT_MONO, 12), height=200, wrap="word")
        self.prompt_text.pack(fill="both", expand=True, pady=(0, 16))
        self.prompt_text.insert("1.0", system_prompt or SYSTEM_PROMPT)

        btn = ctk.CTkFrame(f, fg_color="transparent")
        btn.pack(fill="x")
        ctk.CTkButton(btn, text="恢复默认", command=self._reset_prompt,
                      font=(FONT_FAMILY, 13), fg_color="#555", hover_color="#666", width=110).pack(side="left")
        ctk.CTkButton(btn, text="取消", command=self.destroy,
                      font=(FONT_FAMILY, 13), fg_color="#555", hover_color="#666", width=90).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn, text="保存", command=self._save,
                      font=(FONT_FAMILY, 13), width=90).pack(side="right")

    def _models(self):
        p = self.provider_var.get()
        return AnthropicProvider.models if p == "Anthropic Claude" else OpenAIProvider.models

    def _on_provider_change(self, c):
        if c == "Anthropic Claude":
            self.model_menu.configure(values=AnthropicProvider.models)
            self.model_var.set(AnthropicProvider.default_model)
        else:
            self.model_menu.configure(values=OpenAIProvider.models)
            self.model_var.set(OpenAIProvider.default_model)
        preset = PROVIDER_PRESETS.get(c, {})
        self.base_url_var.set(preset.get("base_url", ""))

    def _save(self):
        self.result = {
            "provider": self.provider_var.get(),
            "api_key": self.api_key_var.get().strip(),
            "model": self.model_var.get(),
            "base_url": self.base_url_var.get().strip(),
            "system_prompt": self.prompt_text.get("1.0", "end-1c"),
        }
        self.destroy()

    def _reset_prompt(self):
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", SYSTEM_PROMPT)


# ── Main Application ──

class AgentApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Agent")
        self.geometry("1280x760")
        self.minsize(960, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

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

        # Tool tracking
        self.tool_status: dict[str, str] = {t: "idle" for t in TOOL_ICONS}
        self.tool_activity: list[dict] = []
        self._active_tool: str | None = None
        self._active_tool_input: dict = {}  # 保存工具调用时的参数，用于结果展示
        self._active_tool_start: float = 0.0
        self._tool_start_time: float = 0.0
        self._last_output_time: float = time.time()
        self._watchdog_armed: bool = False
        self._watchdog_warned: bool = False
        self._stop_requested: bool = False
        self._last_input: str = ""
        self._turn_total: int = 0
        self._turn_done: int = 0
        self._think_buffer: str = ""
        self._think_header_shown: bool = False

        # ── v1.0 升级：滚动指示器 + 思考时间 + diff 渲染 ──
        self._new_msg_count: int = 0               # 滚动到上方后累积的新消息行数
        self._user_scrolled_up: bool = False        # 用户是否滚到了上方
        self._last_scroll_bottom: bool = True       # 滚动条是否在底部
        self._think_start_time: float = 0.0         # 思考开始时间
        self._think_end_time: float = 0.0           # 思考结束时间
        self._thought_displayed: bool = False       # 是否已显示思考时间

        # ── 启动本地 Web 服务器（Monaco Editor 后端）──
        self.web_server = WebServer(agent_app=self)
        self.web_server.start()

        self._build_ui()
        self._load_config()
        self._poll_queue()
        self.entry.focus()

    def __del__(self):
        """清理 Web 服务器资源。"""
        if hasattr(self, 'web_server'):
            try:
                self.web_server.stop()
            except Exception:
                pass

    # ── UI ──

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1, minsize=500)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        # ══ Mission Control Dashboard ══
        self._build_dashboard()

        # ══ Workflow Status Bar ══
        self._build_workflow_bar()

        # ══ Main: Chat + Tool Panel ══
        # Chat（Monaco Editor）
        self.monaco = MonacoChatWidget(self, server_url=self.web_server.get_url())
        self.monaco.grid(row=2, column=0, sticky="nsew", padx=(10, 2), pady=5)
        # ══ Tool Panel ══
        self._build_tool_panel()

        # ══ Quick Action Buttons + Input Area ══
        inp = ctk.CTkFrame(self, corner_radius=0)
        inp.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        inp.grid_columnconfigure(0, weight=1)

        # Action button bar (above input)
        act_frame = ctk.CTkFrame(inp, fg_color="transparent", height=30)
        act_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 0))
        act_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        action_defs = [
            ("⏹", "终止", "Ctrl+Enter", self._stop_agent, "#F44336"),
            ("🔄", "重试", "Ctrl+R", self._retry_last, "#FF9800"),
            ("📋", "复制日志", "", self._copy_chat, "#42A5F5"),
            ("📊", "上下文", "Ctrl+I", self._show_context_detail, "#AB47BC"),
        ]
        self._action_btns = {}
        for i, (icon, label, shortcut, cmd, color) in enumerate(action_defs):
            text = f"{icon} {label}  {shortcut}"
            btn = ctk.CTkButton(act_frame, text=text, font=(FONT_FAMILY, 10),
                                fg_color=color, hover_color=self._darken(color),
                                height=24, corner_radius=4, command=cmd)
            btn.grid(row=0, column=i, padx=1, sticky="ew")
            self._action_btns[label] = btn

        # Input row
        inp_row = ctk.CTkFrame(inp, fg_color="transparent")
        inp_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        inp_row.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(inp_row, placeholder_text="输入指令，Enter 发送",
                                  font=(FONT_MONO, 14), height=40)
        self.entry.grid(row=0, column=0, padx=(10, 8), sticky="ew")
        self.entry.bind("<Return>", self._send)
        self.entry.bind("<Control-Return>", lambda e: self._stop_agent())
        self.entry.bind("<Control-r>", lambda e: self._retry_last())
        self.entry.bind("<Control-R>", lambda e: self._retry_last())
        self.entry.bind("<Control-Shift-S>", lambda e: self._quick_screenshot())
        self.entry.bind("<Control-Shift-s>", lambda e: self._quick_screenshot())
        self.entry.bind("<Control-i>", lambda e: self._show_context_detail())
        self.entry.bind("<Control-I>", lambda e: self._show_context_detail())

        self.send_btn = ctk.CTkButton(inp_row, text="发送", width=90, height=40,
                                      font=(FONT_FAMILY, 14), command=self._send)
        self.send_btn.grid(row=0, column=1, padx=(8, 10))

        # ══ Status Bar ══
        self.status_bar = ctk.CTkLabel(self, text="Ready — configure API in Settings",
                                       anchor="w", font=(FONT_FAMILY, 11), text_color="#888")
        self.status_bar.grid(row=4, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 4))

    def _build_dashboard(self):
        """Build the Mission Control dashboard header."""
        dash = ctk.CTkFrame(self, height=72, corner_radius=0, fg_color="#1a1a2e")
        dash.grid(row=0, column=0, columnspan=2, sticky="ew")
        dash.grid_propagate(False)
        dash.grid_columnconfigure(4, weight=1)  # push buttons to right

        # ── Left: Brand + Status ──
        brand_frame = ctk.CTkFrame(dash, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=(16, 8), pady=8, sticky="w")

        ctk.CTkLabel(brand_frame, text="AgiCode", font=(FONT_FAMILY, 20, "bold"),
                     text_color="#00d4ff").grid(row=0, column=0, sticky="w", pady=(0, 2))

        self.status_indicator = ctk.CTkLabel(brand_frame, text="Idle", font=(FONT_FAMILY, 10),
                                              text_color="#4CAF50", anchor="w")
        self.status_indicator.grid(row=1, column=0, sticky="w")

        # ── Provider + Model ──
        prov_frame = ctk.CTkFrame(dash, fg_color="transparent")
        prov_frame.grid(row=0, column=1, padx=16, pady=8, sticky="w")

        ctk.CTkLabel(prov_frame, text="Provider", font=(FONT_FAMILY, 9),
                     text_color="#666", anchor="w").grid(row=0, column=0, sticky="w")
        self.provider_label = ctk.CTkLabel(prov_frame, text="DeepSeek", font=(FONT_FAMILY, 12),
                                            text_color="#64B5F6", anchor="w")
        self.provider_label.grid(row=1, column=0, sticky="w")

        # ── Session Stats ──
        stats_frame = ctk.CTkFrame(dash, fg_color="transparent")
        stats_frame.grid(row=0, column=2, padx=16, pady=8, sticky="w")

        ctk.CTkLabel(stats_frame, text="Session", font=(FONT_FAMILY, 9),
                     text_color="#666", anchor="w").grid(row=0, column=0, sticky="w")
        self.msg_label = ctk.CTkLabel(stats_frame, text="0 turns", font=(FONT_FAMILY, 12),
                                       text_color="#aaa", anchor="w")
        self.msg_label.grid(row=1, column=0, sticky="w")

        # ── Token Usage ──
        token_frame = ctk.CTkFrame(dash, fg_color="transparent")
        token_frame.grid(row=0, column=3, padx=16, pady=8, sticky="w")

        ctk.CTkLabel(token_frame, text="Context", font=(FONT_FAMILY, 9),
                     text_color="#666", anchor="w").grid(row=0, column=0, sticky="w")
        self.ctx_label = ctk.CTkLabel(token_frame, text="0 / 0K", font=(FONT_MONO, 11),
                                       text_color="#aaa", anchor="w")
        self.ctx_label.grid(row=1, column=0, sticky="w")

        # ── Right: Action Buttons ──
        btn_frame = ctk.CTkFrame(dash, fg_color="transparent")
        btn_frame.grid(row=0, column=5, padx=(8, 16), pady=12, sticky="e")

        ctk.CTkButton(btn_frame, text="Settings", width=74, height=30,
                      font=(FONT_FAMILY, 11), command=self._open_settings,
                      fg_color="#2a2a4a", hover_color="#3a3a5a"
                      ).grid(row=0, column=0, padx=1)

        self.btn_review = ctk.CTkButton(btn_frame, text="🔍 审查", width=64, height=30,
                                        font=(FONT_FAMILY, 11), command=self._open_review,
                                        fg_color="#2a2a4a", hover_color="#3a3a5a")
        self.btn_review.grid(row=0, column=1, padx=1)

        self.btn_research = ctk.CTkButton(btn_frame, text="📊 研究", width=64, height=30,
                                          font=(FONT_FAMILY, 11), command=self._open_research,
                                          fg_color="#2a2a4a", hover_color="#3a3a5a")
        self.btn_research.grid(row=0, column=2, padx=1)

        self.btn_schedule = ctk.CTkButton(btn_frame, text="⏰ 定时", width=64, height=30,
                                          font=(FONT_FAMILY, 11), command=self._open_schedule,
                                          fg_color="#2a2a4a", hover_color="#3a3a5a")
        self.btn_schedule.grid(row=0, column=3, padx=1)

        self.btn_watch = ctk.CTkButton(btn_frame, text="👁 监控", width=64, height=30,
                                       font=(FONT_FAMILY, 11), command=self._open_watch,
                                       fg_color="#2a2a4a", hover_color="#3a3a5a")
        self.btn_watch.grid(row=0, column=4, padx=1)

        ctk.CTkButton(btn_frame, text="Clear", width=60, height=30,
                      font=(FONT_FAMILY, 11), command=self._clear_chat,
                      fg_color="#333", hover_color="#555"
                      ).grid(row=0, column=5, padx=1)

        # ── Context progress bar (thin, below dashboard) ──
        self.ctx_progress = ctk.CTkProgressBar(dash, height=3, corner_radius=0,
                                                fg_color="#333", progress_color="#00d4ff")
        self.ctx_progress.grid(row=1, column=0, columnspan=6, sticky="ew")
        self.ctx_progress.set(0)

    def _build_workflow_bar(self):
        """透明工作流状态栏 —— 显示当前步骤、进度、下一步。"""
        wf = ctk.CTkFrame(self, height=26, corner_radius=0, fg_color="#15152a")
        wf.grid(row=1, column=0, columnspan=2, sticky="ew")
        wf.grid_propagate(False)
        wf.grid_columnconfigure(1, weight=1)

        # 步骤状态文本
        self.wf_label = ctk.CTkLabel(wf, text="⏳ 等待任务...", font=(FONT_FAMILY, 11),
                                      text_color="#888", anchor="w")
        self.wf_label.grid(row=0, column=0, padx=(14, 4), pady=2, sticky="w")

        # 进度条（细线）
        self.wf_progress = ctk.CTkProgressBar(wf, height=3, corner_radius=0,
                                               fg_color="#222", progress_color="#FF9800")
        self.wf_progress.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        self.wf_progress.set(0)

        # 步骤计数
        self.wf_count = ctk.CTkLabel(wf, text="0/0", font=(FONT_MONO, 10),
                                      text_color="#555", anchor="e")
        self.wf_count.grid(row=0, column=2, padx=(4, 14), pady=2, sticky="e")

    def _update_workflow_display(self):
        """从 Agent 的工作流同步 UI 显示。"""
        if not self.agent or not self.agent.workflow:
            self.wf_label.configure(text="⏳ 等待任务...")
            self.wf_progress.set(0)
            self.wf_count.configure(text="0/0")
            return

        wf = self.agent.workflow
        if wf.status == "idle" or not wf.steps:
            self.wf_label.configure(text="⏳ 等待任务...")
            self.wf_progress.set(0)
            self.wf_count.configure(text="0/0")
            return

        prog = wf.progress()
        done = sum(1 for s in wf.steps.values() if s.status == "done")
        total = len(wf.steps)
        status_icon = "▶" if wf.status == "running" else "✅" if wf.status == "done" else "⏹"
        color = "#FFC107" if wf.status == "running" else "#4CAF50" if wf.status == "done" else "#888"

        current = wf.get_current_step()
        next_step = wf.get_next_step_name()
        current_name = current.name if current else ""

        parts = []
        if current_name:
            parts.append(f"▶ {current_name}")
        if next_step:
            parts.append(f"→ {next_step}")
        status_text = " | ".join(parts) if parts else wf.plan_title or "执行中"

        self.wf_label.configure(text=f"{status_icon} {status_text}", text_color=color)
        self.wf_progress.configure(progress_color="#FF9800" if wf.status == "running" else "#4CAF50")
        self.wf_progress.set(prog)
        self.wf_count.configure(text=f"{done}/{total}")

    def _poll_workflow(self):
        """定时轮询工作流状态（由 _poll_queue 驱动）。"""
        self._update_workflow_display()
        if self.busy:
            self.after(500, self._poll_workflow)

    def _build_tool_panel(self):
        """Build the right-side tool panel with tabbed layout (工具 | 日志)."""
        panel = ctk.CTkFrame(self, width=290, corner_radius=8)
        panel.grid(row=2, column=1, sticky="nsew", padx=(2, 10), pady=5)
        panel.grid_propagate(False)
        panel.grid_rowconfigure(2, weight=1)  # tabview

        # ── Header ──
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="🛠 工具面板", font=(FONT_FAMILY, 15, "bold"),
                      anchor="w").grid(row=0, column=0, sticky="w")

        # ── Task Progress Bar ──
        prog_frame = ctk.CTkFrame(panel, fg_color="transparent", height=28)
        prog_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))
        prog_frame.grid_columnconfigure(0, weight=1)
        prog_frame.grid_propagate(False)
        self.task_progress = ctk.CTkProgressBar(prog_frame, height=8, corner_radius=4)
        self.task_progress.grid(row=0, column=0, sticky="ew", pady=(2, 0))
        self.task_progress.set(0)
        self.task_prog_label = ctk.CTkLabel(prog_frame, text="", font=(FONT_MONO, 9),
                                             text_color="#555", anchor="w")
        self.task_prog_label.grid(row=1, column=0, sticky="w")

        # ── Tab View: 工具 | 日志 ──
        self.tab_view = ctk.CTkTabview(panel, fg_color="transparent",
                                       segmented_button_selected_color="#2a2a4a",
                                       segmented_button_unselected_color="#222",
                                       text_color="#e0e0e0",
                                       segmented_button_selected_hover_color="#3a3a5a")
        self.tab_view.grid(row=2, column=0, sticky="nsew", padx=4, pady=(4, 4))

        tab_tools = self.tab_view.add("🛠 工具")
        tab_log = self.tab_view.add("📋 日志")

        # ── Tab: 工具状态 ──
        self.tool_scroll = ctk.CTkScrollableFrame(tab_tools, fg_color="transparent")
        self.tool_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self.tool_scroll.grid_columnconfigure(0, weight=1)

        self.tool_widgets: dict[str, dict] = {}
        row_offset = 0
        for cat_name, tool_names in TOOL_CATEGORIES:
            cat_color = CATEGORY_COLORS.get(cat_name, "#888")
            cat_hdr = ctk.CTkFrame(self.tool_scroll, fg_color="#333333", height=26, corner_radius=4)
            cat_hdr.grid(row=row_offset, column=0, sticky="ew", pady=(6, 1))
            cat_hdr.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cat_hdr, text=cat_name, font=(FONT_FAMILY, 11, "bold"),
                          text_color=cat_color, anchor="w").grid(row=0, column=0, padx=10, pady=2, sticky="w")
            row_offset += 1
            pairs = [tool_names[i:i+2] for i in range(0, len(tool_names), 2)]
            for pair in pairs:
                tag_row = ctk.CTkFrame(self.tool_scroll, fg_color="transparent", height=32)
                tag_row.grid(row=row_offset, column=0, sticky="ew", pady=1)
                tag_row.grid_columnconfigure(0, weight=1), tag_row.grid_columnconfigure(1, weight=1)
                row_offset += 1
                for ci, tname in enumerate(pair):
                    icon = TOOL_ICONS.get(tname, "🔹")
                    frame = ctk.CTkFrame(tag_row, fg_color="#2a2a2a", corner_radius=6, height=30)
                    frame.grid(row=0, column=ci, sticky="ew", padx=2)
                    frame.grid_propagate(False)
                    frame.grid_columnconfigure(1, weight=1)
                    dot = ctk.CTkLabel(frame, text="○", font=(FONT_MONO, 9),
                                       text_color=COLOR_TOOL_IDLE, width=12)
                    dot.grid(row=0, column=0, padx=(6, 2), pady=5)
                    ctk.CTkLabel(frame, text=f"{icon} {tname}",
                                 font=(FONT_MONO, 11, "bold"), anchor="w"
                                 ).grid(row=0, column=1, padx=0, pady=5, sticky="w")
                    ctk.CTkLabel(frame, text=TOOL_DESCRIPTIONS.get(tname, ""),
                                 font=(FONT_FAMILY, 9), text_color="#666", anchor="e"
                                 ).grid(row=0, column=2, padx=(2, 6), pady=5)
                    self.tool_widgets[tname] = {"dot": dot, "card": frame}
            ctk.CTkLabel(self.tool_scroll, text="", font=(FONT_MONO, 3)).grid(row=row_offset, column=0)
            row_offset += 1

        # ── Tab: 活动日志 ──
        self.activity_log = tk.Text(tab_log, wrap="word", font=(FONT_MONO, 11),
                                     bg="#1a1a1a", fg="#aaa", borderwidth=0,
                                     highlightthickness=0, padx=8, pady=6,
                                     state="disabled", relief="flat")
        self.activity_log.pack(fill="both", expand=True, padx=4, pady=4)
        self.activity_log.tag_config("log_idle", foreground="#555")
        self.activity_log.tag_config("log_run", foreground="#FFC107")
        self.activity_log.tag_config("log_done", foreground="#4CAF50")
        self.activity_log.tag_config("log_err", foreground="#F44336")

    # ── Tool Panel Updates ──

    def _set_tool_status(self, name: str, status: str):
        """Update a tool's status dot in the panel."""
        self.tool_status[name] = status
        w = self.tool_widgets.get(name)
        if not w:
            return
        color = {
            "idle": COLOR_TOOL_IDLE, "running": COLOR_TOOL_RUNNING,
            "done": COLOR_TOOL_DONE, "error": COLOR_TOOL_ERROR,
        }.get(status, COLOR_TOOL_IDLE)
        dots = {"idle": "○", "running": "●", "done": "✓", "error": "✗"}
        w["dot"].configure(text=dots.get(status, "○"), text_color=color)

    def _log_activity(self, tool: str, status: str, detail: str = ""):
        """Add a line to the activity log."""
        ts = time.strftime("%H:%M:%S")
        icon = {"running": "▶", "done": "✓", "error": "✗"}.get(status, "·")
        tag = f"log_{status}" if status in ("run", "done", "err") else "log_idle"
        line = f"{ts} {icon} {tool}"
        if detail:
            line += f"  {detail[:60]}"
        self.activity_log.configure(state="normal")
        self.activity_log.insert("end", line + "\n", tag)
        self.activity_log.see("end")
        self.activity_log.configure(state="disabled")

    def _reset_task_progress(self):
        """Clear task progress bar."""
        self._turn_total = 0
        self._turn_done = 0
        self.task_progress.set(0)
        self.task_prog_label.configure(text="")

    def _update_task_progress(self):
        """Update task step progress bar."""
        if self._turn_total <= 0:
            self.task_progress.set(0)
            self.task_prog_label.configure(text="")
            return
        ratio = min(self._turn_done / self._turn_total, 1.0)
        self.task_progress.set(ratio)
        color = "#4CAF50" if ratio >= 1.0 else "#FFC107"
        self.task_progress.configure(progress_color=color)
        self.task_prog_label.configure(text=f"步骤 {self._turn_done}/{self._turn_total}")

    def _update_context_bar(self):
        """Update the context usage progress bar with current token counts.

        v1.0: Shows "82% context used" style indicator like AI coding assistants.
        """
        if not self.agent or not self.agent.messages:
            self.ctx_progress.set(0)
            self.ctx_label.configure(text="0 / 0K tokens")
            return
        try:
            from .context import count_total_tokens, get_context_limit
            system = self.agent.system_prompt or ""
            total = count_total_tokens(self.agent.messages, system)
            model_name = getattr(self.agent.provider, 'model_name', '') or ''
            limit = get_context_limit(model_name)
            ratio = min(total / limit, 1.0) if limit > 0 else 0
            pct = int(ratio * 100)
            self.ctx_progress.set(ratio)
            if ratio > 0.85:
                self.ctx_progress.configure(progress_color="#F44336")
                color = "#F44336"
            elif ratio > 0.65:
                self.ctx_progress.configure(progress_color="#FF9800")
                color = "#FF9800"
            else:
                self.ctx_progress.configure(progress_color="#4CAF50")
                color = "#aaa"
            # Claude Code 风格: "82% context used"
            self.ctx_label.configure(
                text=f"{pct}% context used",
                text_color=color,
            )
        except Exception:
            pass

    # ── Config ──

    def _config_path(self):
        return os.path.join(os.path.dirname(__file__), "..", "config.json")

    def _load_config(self):
        p = self._config_path()
        if os.path.exists(p):
            try:
                d = json.load(open(p, "r", encoding="utf-8"))
                self.provider_name = d.get("provider", get_default_provider())
                self.api_key = d.get("api_key", "")
                self.model = d.get("model", "")
                self.base_url = d.get("base_url", "")
                # MCP 服务器配置（传递到 Agent 工具系统）
                self._mcp_servers = d.get("mcp_servers", [])
                # 系统提示词始终从 prompt.py 加载，config 不覆盖
                self._init_agent()
            except Exception:
                pass

    def _save_config(self):
        try:
            with open(self._config_path(), "w", encoding="utf-8") as f:
                json.dump({"provider": self.provider_name, "api_key": self.api_key,
                           "model": self.model, "base_url": self.base_url},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _init_agent(self):
        if not self.api_key:
            return
        try:
            # 创建透明事件总线 + 工作流状态机
            self.transcript = Transcript(agent_id="agicode-gui")
            def _on_transcript(event):
                # 部分事件推动 UI 更新
                if event.type in ("step", "phase", "tool", "loop"):
                    self.after_idle(self._update_workflow_display)
            self.transcript.on("*", _on_transcript)

            # Agent 配置（v1.0 透明 + MCP）
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
            self.provider_label.configure(text=self.provider_name)

            # Show memory stats if available
            try:
                from .memory import get_conversation_stats, get_codebase_stats
                cs = get_conversation_stats()
                cbs = get_codebase_stats()
                mem_parts = []
                if cs.get("total_turns"):
                    mem_parts.append(f"记忆:{cs['total_turns']}轮")
                if cbs.get("cached_modules"):
                    mem_parts.append(f"缓存:{cbs['cached_modules']}模块")
                if mem_parts:
                    self.status_bar.configure(text="就绪 — " + " | ".join(mem_parts))
            except Exception:
                pass
            self._update_context_bar()
        except Exception as e:
            self.status_bar.configure(text=f"初始化失败: {e}")

    # ── Quick Actions ──

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.75) -> str:
        """Darken a hex color by factor."""
        r = int(int(hex_color[1:3], 16) * factor)
        g = int(int(hex_color[3:5], 16) * factor)
        b = int(int(hex_color[5:7], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _stop_agent(self):
        """Immediately stop the current agent generation."""
        if not self.busy:
            return
        self._force_reset("⏹ 用户手动终止")

    def _retry_last(self):
        """Re-send the last user input."""
        if self.busy or not self._last_input:
            return
        self._send_text(self._last_input)

    def _quick_screenshot(self):
        """Send a screenshot command to the agent."""
        if self.busy or not self.api_key:
            return
        self._send_text("截屏，然后告诉我你看到了什么")

    def _show_context_detail(self):
        """Show detailed context breakdown in the chat."""
        if not self.agent:
            self._chat_line("尚无对话", "err")
            return
        try:
            from .context import count_total_tokens, count_message_tokens, count_tool_result_tokens, get_context_limit
            system = self.agent.system_prompt or ""
            total = count_total_tokens(self.agent.messages, system)
            model_name = getattr(self.agent.provider, 'model_name', '') or ''
            limit = get_context_limit(model_name)

            lines = [f"── 上下文明细 ──", f"模型限额: {limit/1000:.0f}K tokens"]
            lines.append(f"总使用:   {total/1000:.1f}K tokens ({total/limit*100:.1f}%)")
            lines.append(f"系统提示词: ~{len(system)//4} tokens")
            # Count by role
            roles: dict[str, int] = {}
            for m in self.agent.messages:
                r = m.get("role", "?")
                if r in ("user", "assistant"):
                    roles[r] = roles.get(r, 0) + count_message_tokens(m)
                elif r == "tool":
                    roles[r] = roles.get(r, 0) + count_tool_result_tokens(m)
            for r, c in roles.items():
                lines.append(f"  {r}: {c/1000:.1f}K")
            lines.append(f"消息条数: {len(self.agent.messages)}")
            for line in lines:
                self._chat_line(line, "sys")
        except Exception as e:
            self._chat_line(f"上下文分析失败: {e}", "err")

    def _copy_chat(self):
        """一键复制全部对话/输出到剪贴板。"""
        try:
            content = self.monaco.get_content()
            if not content.strip():
                self._chat_line("没有可复制的内容", "dim")
                return
            self.clipboard_clear()
            self.clipboard_append(content)
            self.status_bar.configure(text="✅ 已复制到剪贴板，可直接粘贴给分析助手")
            self.after(3000, lambda: self.status_bar.configure(
                text="就绪" if not self.busy else "工作中..."))
        except Exception as e:
            self._chat_line(f"复制失败: {e}", "err")

    # ── v1.0：滚动管理 ──

    def _is_scroll_at_bottom(self) -> bool:
        """通过 Monaco 查询滚动条是否在底部。"""
        try:
            state = self.monaco.get_scroll_state()
            return state.get("atBottom", True)
        except Exception:
            return True

    def _scroll_to_bottom(self):
        """滚动到底部并隐藏指示器。"""
        self.monaco.scroll_to_bottom()
        self._new_msg_count = 0
        self._user_scrolled_up = False
        self._last_scroll_bottom = True

    def _update_scroll_indicator(self):
        """滚动指示器由 Monaco 前端管理，此方法保留为兼容接口。"""
        pass

    # ── Queue ──

    def _on_complete(self):
        self.busy = False
        self._watchdog_armed = False
        self._watchdog_warned = False
        self._stop_requested = False
        self.entry.configure(state="normal")
        self.send_btn.configure(state="normal", text="发送")
        self._set_action_buttons(False)
        self.status_indicator.configure(text="Idle", text_color="#4CAF50")
        self.entry.focus()
        n = len(self.agent.messages) // 2 if self.agent else 0
        self.msg_label.configure(text=f"{n} 轮")
        self._update_context_bar()
        self._update_task_progress()
        self.after(2000, self._reset_task_progress)
        if self._active_tool:
            self._set_tool_status(self._active_tool, "done")
            self._active_tool = None
        # ── 显示思考耗时 ──
        if self._think_start_time > 0:
            elapsed = time.time() - self._think_start_time
            if elapsed >= 1.0:
                unit = "s" if elapsed < 60 else "m"
                val = elapsed if elapsed < 60 else elapsed / 60
                self._chat_line(f"  🧠 思考 {val:.1f}{unit}", "dim")
        self._think_start_time = 0.0
        # 注入最终工作流总结
        if self.agent and self.agent.workflow and self.agent.workflow.steps:
            wf = self.agent.workflow
            done = sum(1 for s in wf.steps.values() if s.status == "done")
            total = len(wf.steps)
            if done == total:
                self._chat_line(f"  ✅ 所有步骤完成 ({done}/{total}) — 任务结束", "sys")
            else:
                failed = sum(1 for s in wf.steps.values() if s.status == "failed")
                parts = [f"  📊 步骤: {done}/{total} 完成"]
                if failed:
                    parts.append(f"  ❌ {failed} 步失败")
                self._chat_line(" | ".join(parts), "sys")

    def _poll_queue(self):
        """Poll UI message queue. Limits per-cycle processing to keep UI responsive."""
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

        # ── Watchdog: detect stuck, show running duration ──
        if self.busy and self._watchdog_armed:
            elapsed = time.time() - self._last_output_time
            if self._active_tool == "bash":
                warn_threshold = 300
                reset_threshold = 600
            else:
                warn_threshold = 180
                reset_threshold = 300

            # 注意: reset 条件必须在前，否则 elapsed 超过 reset 阈值时
            # 永远不会进入 reset 逻辑（因为 warn 条件先匹配）
            if elapsed > reset_threshold:
                self._force_reset("检测到 Agent 卡死（300s 无输出），已自动重置")
            elif elapsed > warn_threshold and not self._watchdog_warned:
                self._watchdog_warned = True
                self.status_indicator.configure(text=f"⚠ 工作中 ({int(elapsed)}s 无响应)", text_color="#F44336")
                self._chat_line(f"⚠ 警告: Agent 已 {int(elapsed)}s 无输出，可能已卡死", "err")
            elif elapsed > warn_threshold:
                self.status_indicator.configure(text=f"⚠ 工作中 ({int(elapsed)}s)", text_color="#FF9800")
            elif self._active_tool and self._active_tool_start:
                # Show running duration for active tool
                run_sec = int(time.time() - self._active_tool_start)
                if run_sec > 0:
                    curr = self.status_indicator.cget("text")
                    # Only update duration display, preserve the tool name set in tool_start
                    if "(" not in curr or "工作中" in curr:
                        pass  # already handled above

        # ── Workflow status display ──
        self._update_workflow_display()

        self.after(250, self._poll_queue)

    def _force_reset(self, reason: str = ""):
        """Force-reset the agent when stuck."""
        self.busy = False
        self._watchdog_armed = False
        self._watchdog_warned = False
        self._stop_requested = False
        # Sanitize message list: remove orphan tool_calls from broken state
        if self.agent:
            try:
                from .context import sanitize_messages
                self.agent.messages = sanitize_messages(self.agent.messages)
            except Exception:
                pass
        self.entry.configure(state="normal")
        self.send_btn.configure(state="normal", text="发送")
        self._set_action_buttons(False)
        self.status_indicator.configure(text="Idle", text_color="#4CAF50")
        self._reset_task_progress()
        if reason:
            self._chat_line(f"⛔ {reason}", "err")
            self.status_bar.configure(text=reason)
        self.entry.focus()

    def _handle_msg(self, t: str, d: Any):
        self._last_output_time = time.time()
        self._watchdog_armed = True
        self._watchdog_warned = False
        if t == "text":
            self._chat_stream(d, "asst")
        elif t == "thinking":
            # 紧凑显示：只显示开头一段，不刷屏
            if not hasattr(self, '_think_buffer'):
                self._think_buffer = ""
                self._think_header_shown = False
            self._think_buffer += d
            if not self._think_header_shown and len(self._think_buffer) > 20:
                self._think_header_shown = True
                preview = self._think_buffer[:100].replace("\n", " ")
                self._chat_line(f"  🧠 思考: {preview}...", "think")
        elif t == "tool_start":
            name, inp = d
            # 避免重复显示：streaming 阶段先发空{}，core.py 执行循环再发真实参数
            if self._active_tool == name:
                # 第二次调用：只更新参数，不重复显示
                self._active_tool_input = inp
            else:
                # 上一个工具完成
                if self._active_tool:
                    self._set_tool_status(self._active_tool, "done")
                self._active_tool = name
                self._active_tool_input = inp
                self._active_tool_start = time.time()
                self._set_tool_status(name, "running")
                self._log_activity(name, "running", json.dumps(inp, ensure_ascii=False)[:80])
                # 显示步骤编号（如 [1/3]）
                step_prefix = ""
                if self._turn_total > 1:
                    step_num = self._turn_done + 1
                    step_prefix = f"  [{step_num}/{self._turn_total}]"
                self._append_tool(name, inp, step_prefix)

            # 状态栏更新
            verb = TOOL_DESCRIPTIONS.get(name, name)
            cmd_preview = ""
            if name == "bash" and "command" in inp:
                cmd_preview = inp["command"][:60]
            elif "file_path" in inp:
                cmd_preview = inp["file_path"]
            if cmd_preview:
                self.status_indicator.configure(text=f"{verb}: {cmd_preview}", text_color="#FF9800")
            else:
                self.status_indicator.configure(text=f"{verb}...", text_color="#FF9800")
        elif t == "tool_result":
            self._turn_done += 1
            self._update_task_progress()
            self._append_tool_result(d)
            # 补充进度显示
            if self._turn_total > 1:
                self._chat_line(f"    → 步骤 {self._turn_done}/{self._turn_total}", "dim")
        elif t == "tool_output":
            self._chat_stream(d, "tool_r", scroll=True)
        elif t == "heartbeat":
            # Silent heartbeat from bash streaming — updates watchdog timer, no display
            pass
        elif t == "turn_plan":
            self._turn_total = d
            self._turn_done = 0
            self._update_task_progress()
            if d > 1:
                self._chat_line(f"  📋 计划执行 {d} 个步骤", "sys")
        elif t == "error":
            if self._active_tool:
                self._set_tool_status(self._active_tool, "error")
                self._log_activity(self._active_tool, "error", str(d)[:60])
                self._active_tool = None
            self._chat_line(f"错误: {d}", "err")
        elif t == "turn_end":
            self._chat_line("", "sep")
            # 在轮次结束时刷新工作流显示 + 注入下一步摘要
            self._update_workflow_display()
            self._inject_turn_summary()
        elif t == "complete":
            self._on_complete()

    # ── Chat Display ──

    def _chat_stream(self, text: str, tag: str, scroll: bool = True):
        """流式文本渲染：通过 Monaco Editor 桥接显示。"""
        # 样式映射表（tk tags → monaco styles）
        style_map = {
            "asst": "assistant", "user_c": "assistant",
            "think": "thinking", "tool_r": "tool_result",
            "tool": "tool", "err": "err", "sys": "sys",
            "dim": "dim", "sep": "sep", "code": "code",
        }
        style = style_map.get(tag, "assistant")
        self.monaco.append_text(text, style)

        if not self._is_scroll_at_bottom() and scroll:
            new_lines = text.count("\n")
            self._new_msg_count += new_lines
            self._update_scroll_indicator()

    def _render_markdown_stream(self, text: str, tag: str):
        """Monaco Editor 原生支持语法高亮，此方法不再需要。"""
        self._chat_stream(text, tag)

    def _chat_line(self, text: str, tag: str = ""):
        style_map = {
            "user": "user", "user_c": "assistant",
            "asst": "assistant", "think": "thinking",
            "tool": "tool", "tool_r": "tool_result",
            "err": "err", "sys": "sys", "dim": "dim",
            "sep": "sep", "code": "code",
        }
        style = style_map.get(tag, "assistant")
        self.monaco.append_line(text, style)
        if not self._is_scroll_at_bottom():
            self._new_msg_count += 1
            self._update_scroll_indicator()

    def _append_user_msg(self, text: str):
        """在 Monaco 编辑器中显示用户消息。"""
        self.monaco.append_line(f">>> {text}", "user")

    def _tool_label(self, name: str) -> str:
        """Get icon + label for a tool name."""
        icons = {
            "read": "📖", "write": "✏️", "edit": "🔧", "replace": "🔍",
            "glob": "🔎", "grep": "🔎", "bash": "💻", "web": "🌐",
            "web_search": "🔍", "browser": "🌍", "process": "⚙️",
            "service": "⚙️", "registry": "📋", "gui": "🖱️",
            "plan": "📋", "task": "✅", "background": "⏳",
            "remember": "🧠", "test": "🧪", "dep": "📦",
            "ast": "🌳", "dep_graph": "🕸️", "call_chain": "🔗",
            "monitor": "📊", "schedule": "⏰", "watch": "👁️",
            "websocket": "🔌", "download": "📥", "move": "📂",
            "copy": "📄", "delete": "🗑️", "mkdir": "📁",
            "ask_user": "💬", "trace_error": "🐛",
        }
        return icons.get(name, "⚡")

    def _tool_path_display(self, inp: dict) -> str:
        """从工具参数中提取要显示的目标路径/命令。"""
        if "file_path" in inp:
            return inp["file_path"]
        if "command" in inp:
            cmd = inp["command"]
            return cmd[:80] + ("..." if len(cmd) > 80 else "")
        if "url" in inp:
            return inp["url"]
        if "pattern" in inp:
            return inp["pattern"]
        if "query" in inp:
            return inp["query"]
        if "path" in inp:
            return inp["path"]
        return ""

    def _append_tool(self, name: str, inp: dict, step_prefix: str = ""):
        """Claude Code 风格：通过 Monaco 桥接显示工具调用。"""
        self.monaco.append_tool_start(name, inp, step_prefix)
        # 额外参数用 dim 样式显示
        extra = {k: v for k, v in inp.items()
                 if k not in ("file_path", "command", "url", "pattern", "query", "path", "content") and v}
        if extra:
            meta = "    " + " ".join(f"{k}={v}" for k, v in extra.items())
            if len(meta) > 150:
                meta = meta[:150] + "..."
            self.monaco.append_line(meta, "dim")

    def _append_tool_result(self, result: str):
        """通过 Monaco 桥接显示工具结果 + 耗时 + 差异比较。"""
        is_err = any(kw in result[:100].lower() for kw in ("错误", "error", "失败", "❌"))
        current_tool = self._active_tool or ""
        current_inp = self._active_tool_input or {}

        elapsed = ""
        if self._active_tool_start:
            sec = time.time() - self._active_tool_start
            elapsed = f" ({sec:.1f}s)" if sec < 60 else f" ({sec/60:.1f}m)"

        # 通过 Monaco 桥接显示工具结果（含 diff 自动检测）
        self.monaco.append_tool_result(result, current_tool, elapsed, current_inp)

        # 错误处理
        if is_err:
            if current_tool:
                self._set_tool_status(current_tool, "error")
                self._log_activity(current_tool, "error", result[:80].replace("\n", " "))
                self._active_tool = None
                self._active_tool_input = {}
            return

        # ── 下一步建议（从工作流获取）──
        self._inject_next_step_hint(current_tool)

        # 更新工具状态面板
        if current_tool:
            self._set_tool_status(current_tool, "done")
            self._log_activity(current_tool, "done", result[:80].replace("\n", " "))
            self._active_tool = None
            self._active_tool_input = {}

    def _inject_next_step_hint(self, completed_tool: str):
        """步骤完成后，展示一句话总结 + 下一步建议。"""
        if not self.agent or not self.agent.workflow:
            return
        wf = self.agent.workflow
        if not wf.steps or wf.status != "running":
            return
        current = wf.get_current_step()
        next_name = wf.get_next_step_name()
        if current:
            done_count = sum(1 for s in wf.steps.values() if s.status == "done")
            total = len(wf.steps)
            step_icon = "✅" if current.status == "done" else "❌"
            self.monaco.append_line(
                f"  {step_icon} 步骤 \"{current.name}\" 完成 ({done_count}/{total})", "sys")
        if next_name:
            self.monaco.append_line(f"  → 下一步: {next_name}", "tool")

    def _inject_turn_summary(self):
        """每轮结束时注入一句话总结 + 下一步建议（Claude Code 风格）。"""
        if not self.agent or not self.agent.workflow:
            return
        wf = self.agent.workflow
        if not wf.steps or wf.status != "running":
            return
        current = wf.get_current_step()
        if not current:
            return
        out = []
        done = sum(1 for s in wf.steps.values() if s.status == "done")
        total = len(wf.steps)
        out.append(f"  📊 进度: {done}/{total}")
        if current.status == "running":
            out.append(f"  ▶ 当前: {current.name}")
        next_name = wf.get_next_step_name()
        if next_name:
            out.append(f"  ⏭ 下一步: {next_name}")
        elif done == total and wf.status == "running":
            out.append(f"  ✅ 所有步骤已完成")
            wf.status = "done"
        if len(out) > 1:
            for line in out:
                self.monaco.append_line(line, "sys")

    # ── Actions ──

    def _send(self, event=None):
        if self.busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self._send_text(text)

    def _set_action_buttons(self, busy: bool):
        """Enable/disable quick action buttons based on busy state."""
        for label, btn in self._action_btns.items():
            if label == "终止":
                btn.configure(state="normal" if busy else "disabled")
            else:
                btn.configure(state="disabled" if busy else "normal")

    def _send_text(self, text: str):
        """Send text to the agent. Shared by _send and quick actions."""
        if self.busy:
            return
        if not self.api_key:
            self._chat_line("请先点击 ⚙ 设置 配置 API Key", "err")
            return
        if not self.agent:
            self._init_agent()
            if not self.agent:
                self._chat_line("Agent 初始化失败，请检查设置", "err")
                return

        self._last_input = text
        self.entry.delete(0, "end")
        self.entry.configure(state="disabled")
        self.send_btn.configure(state="disabled", text="工作中...")
        self.busy = True
        self._set_action_buttons(True)
        self.status_indicator.configure(text="Thinking", text_color="#FF9800")
        self._append_user_msg(text)
        # 重置思考缓冲区
        self._think_buffer = ""
        self._think_header_shown = False
        # 记录思考开始时间
        self._think_start_time = time.time()

        # Reset tool statuses
        for t in self.tool_status:
            self._set_tool_status(t, "idle")

        t = threading.Thread(target=self._run_thread, args=(text,), daemon=True)
        t.start()

    def _run_thread(self, text: str):
        try:
            h = UIStreamHandler(self.ui_queue)
            self.agent.run_iteration(text, h)
        except Exception as e:
            self.ui_queue.put(("error", str(e)))
            self.ui_queue.put(("complete", None))

    def _open_settings(self):
        d = SettingsDialog(self, provider_name=self.provider_name, api_key=self.api_key,
                           model=self.model, base_url=self.base_url,
                           system_prompt=self.system_prompt)
        self.wait_window(d)
        if not d.result:
            return
        self.provider_name = d.result["provider"]
        self.api_key = d.result["api_key"]
        self.model = d.result["model"]
        self.base_url = d.result.get("base_url", "")
        self.system_prompt = d.result["system_prompt"]
        self._init_agent()
        self._save_config()
        parts = [f"Key: {self.api_key[:8]}..."] if self.api_key else []
        parts.append(f"{self.provider_name}/{self.model}")
        self.status_bar.configure(text="就绪 — " + " | ".join(parts))
        self.msg_label.configure(text=f"{len(self.agent.messages)//2 if self.agent else 0} 轮")

    def _clear_chat(self):
        self.monaco.clear_chat()
        # Clear activity log
        self.activity_log.configure(state="normal")
        self.activity_log.delete("1.0", "end")
        self.activity_log.configure(state="disabled")
        if self.agent:
            self.agent.messages = []
        self.msg_label.configure(text="0 轮")
        for t in self.tool_status:
            self._set_tool_status(t, "idle")

    # ── New Feature Dialogs ──

    def _open_review(self):
        if not self.agent or not self.api_key:
            self._chat_line("请先配置 API Key", "err")
            return
        CodeReviewDialog(self, self.agent, None)

    def _open_research(self):
        if not self.agent or not self.api_key:
            self._chat_line("请先配置 API Key", "err")
            return
        ResearchDialog(self, self.agent, None)

    def _open_schedule(self):
        SchedulerDialog(self, get_scheduler())

    def _open_watch(self):
        WatcherDialog(self, get_watcher())


def run():
    AgentApp().mainloop()


if __name__ == "__main__":
    run()
