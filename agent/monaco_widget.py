"""monaco_widget — WebView2 嵌入控件，封装 Monaco Editor。

将 Edge WebView2 嵌入 customtkinter Frame，
通过 evaluate_js() 实现 Python ↔ JavaScript 双向通信。

用法:
    widget = MonacoChatWidget(parent_frame, server_url="http://127.0.0.1:12345")
    widget.pack(fill="both", expand=True)
    widget.append_text("Hello", "assistant")
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import customtkinter as ctk


class MonacoChatWidget(ctk.CTkFrame):
    """嵌入 WebView2 的 Monaco Editor 聊天控件。

    通过 evaluate_js 调用前端 AgiCodeBridge API，
    在 Monaco Editor 中渲染流式文本、工具调用、差异比较等内容。
    """

    def __init__(self, parent, server_url: str = "", **kwargs):
        super().__init__(parent, **kwargs)
        self.server_url = server_url
        self._webview: Any = None
        self._ready: bool = False
        self._pending: list[str] = []
        self._init_webview()

    # ── WebView2 初始化 ──

    def _init_webview(self):
        """使用 tkwebview2 创建嵌入式 WebView2 控件。"""
        try:
            # 延迟导入，避免启动时加载失败
            from tkwebview2 import WebView2Frame

            self._webview = WebView2Frame(self)
            self._webview.pack(fill="both", expand=True)

            if self.server_url:
                self._webview.load_url(self.server_url)

            # 轮询就绪状态
            self._poll_ready()

        except ImportError:
            self._show_fallback(
                "WebView2 初始化失败\n\n"
                "运行: pip install tkwebview2\n"
                "需要 Windows 10 1803+ 及 Edge WebView2 Runtime"
            )
        except Exception as e:
            self._show_fallback(f"WebView2 初始化失败: {e}")

    def _poll_ready(self, attempts: int = 0):
        """轮询前端 Monaco Editor 是否就绪。"""
        if attempts > 100:  # 最多等 25 秒
            self._ready = True
            self._flush_pending()
            return

        if self._webview and hasattr(self._webview, "execute_script"):
            try:
                result = self._webview.execute_script(
                    "window.__monacoReady ? 'ready' : 'waiting'"
                )
                if result == "ready":
                    self._ready = True
                    self._flush_pending()
                    return
            except Exception:
                pass

        self.after(250, lambda: self._poll_ready(attempts + 1))

    def _flush_pending(self):
        """刷新所有排队中的 evaluate_js 调用。"""
        for script in self._pending:
            try:
                self._evaluate_js_impl(script)
            except Exception:
                pass
        self._pending.clear()

    # ── JS 执行 ──

    def evaluate_js(self, script: str) -> Any:
        """在 WebView2 中执行 JavaScript。

        如果页面尚未加载完毕，将脚本排队等待。
        """
        if not self._ready:
            self._pending.append(script)
            return None
        return self._evaluate_js_impl(script)

    def _evaluate_js_impl(self, script: str) -> Any:
        """实际执行 JavaScript 的实现。"""
        if self._webview and hasattr(self._webview, "execute_script"):
            try:
                return self._webview.execute_script(script)
            except Exception:
                return None
        return None

    # ── Bridge: Chat 渲染 ──

    def append_text(self, text: str, style: str = "assistant"):
        """在 Monaco 编辑器中追加格式化文本。

        Args:
            text: 要显示的文本
            style: 样式类型（assistant, user, thinking, tool, err 等）
        """
        safe = json.dumps(text)
        self.evaluate_js(f"AgiCodeBridge.appendText({safe}, '{style}')")

    def append_line(self, text: str, style: str = "assistant"):
        """追加一行文本。"""
        safe = json.dumps(text)
        self.evaluate_js(f"AgiCodeBridge.appendLine({safe}, '{style}')")

    # ── Bridge: 工具渲染 ──

    def append_tool_start(self, name: str, input_data: dict, step_prefix: str = ""):
        """显示工具调用开始行。

        Args:
            name: 工具名称（如 "read", "bash"）
            input_data: 工具参数字典
            step_prefix: 步骤编号前缀（如 "[1/3]"）
        """
        safe_name = json.dumps(name)
        safe_input = json.dumps(input_data)
        safe_prefix = json.dumps(step_prefix)
        self.evaluate_js(
            f"AgiCodeBridge.appendToolStart({safe_name}, {safe_input}, {safe_prefix})"
        )

    def append_tool_result(self, result: str, tool_name: str = "",
                            elapsed: str = "", active_input: dict | None = None):
        """显示工具执行结果。

        Args:
            result: 工具返回的字符串
            tool_name: 工具名称
            elapsed: 耗时文本（如 " (0.3s)"）
            active_input: 调用参数（用于 diff 检测）
        """
        safe_result = json.dumps(result)
        safe_name = json.dumps(tool_name)
        safe_elapsed = json.dumps(elapsed)

        self.evaluate_js(
            f"AgiCodeBridge.appendToolResult({safe_result}, {safe_name}, {safe_elapsed}, {{}})"
        )

        # 如果包含 diff 标记，自动触发 diff 渲染
        if "--- DIFF START ---" in result:
            file_path = ""
            if active_input and "file_path" in active_input:
                file_path = active_input["file_path"]
            safe_fp = json.dumps(file_path)
            self.evaluate_js(
                f"AgiCodeBridge.openDiffFromUnified({safe_result}, {safe_fp})"
            )

    # ── Bridge: Diff ──

    def open_diff(self, diff_text: str, file_path: str = ""):
        """在 diff 编辑器中显示差异比较。"""
        safe_diff = json.dumps(diff_text)
        safe_fp = json.dumps(file_path)
        self.evaluate_js(
            f"AgiCodeBridge.openDiffFromUnified({safe_diff}, {safe_fp})"
        )

    # ── Bridge: 其他 ──

    def clear_chat(self):
        """清空聊天内容。"""
        self.evaluate_js("AgiCodeBridge.clearChat()")

    def scroll_to_bottom(self):
        """滚动到编辑器底部。"""
        self.evaluate_js("AgiCodeBridge.scrollToBottom()")

    def set_status(self, text: str):
        """设置状态文本（前端兼容接口）。"""
        safe = json.dumps(text)
        self.evaluate_js(f"AgiCodeBridge.setStatus({safe})")

    def get_scroll_state(self) -> dict:
        """获取滚动状态。

        Returns:
            {"atBottom": bool, "scrollTop": int}
        """
        try:
            result = self.evaluate_js("AgiCodeBridge.getScrollState()")
            if result:
                return json.loads(result) if isinstance(result, str) else result
        except Exception:
            pass
        return {"atBottom": True, "scrollTop": 0}

    def get_content(self) -> str:
        """获取 Monaco 编辑器的全部内容。"""
        try:
            result = self.evaluate_js("AgiCodeBridge.getContent()")
            return result if isinstance(result, str) else ""
        except Exception:
            return ""

    # ── 生命周期 ──

    def navigate(self, url: str):
        """导航到指定 URL。"""
        self.server_url = url
        if self._webview and hasattr(self._webview, "load_url"):
            self._webview.load_url(url)

    def destroy(self):
        """清理 WebView2 资源。"""
        self._webview = None
        self._ready = False
        self._pending.clear()
        super().destroy()

    # ── 回退显示 ──

    def _show_fallback(self, message: str):
        """当 WebView2 不可用时显示错误信息。"""
        import tkinter as tk
        self._ready = True  # 允许操作继续
        text = tk.Text(self, wrap="word", font=("Consolas", 12),
                       bg="#1e1e1e", fg="#e0e0e0", borderwidth=0,
                       padx=14, pady=12, state="disabled", relief="flat")
        text.pack(fill="both", expand=True)
        text.configure(state="normal")
        text.insert("end", message, ("err",))
        text.tag_config("err", foreground="#F44336")
        text.configure(state="disabled")
