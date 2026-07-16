"""AgiCode Web — 纯网页版入口。

启动流程：
  1. 加载配置 config.json
  2. 创建 Agent 实例
  3. 启动 FastAPI 本地服务器 (随机端口)
  4. 自动打开浏览器

无 tkinter 依赖，纯 HTTP + SSE 驱动。
"""

from __future__ import annotations

import json
import os
import threading
import time
import webbrowser

from .core import Agent, StreamHandler
from .prompt import SYSTEM_PROMPT
from .providers import AnthropicProvider, OpenAIProvider
from .web_server import WebServer


TOOL_ICONS = {
    "read": "📖", "write": "✏️", "edit": "🔧",
    "glob": "🔍", "grep": "🔎", "bash": "💻",
    "process": "⚙️", "web": "🌐", "browser": "🌍",
    "background": "⏳", "plan": "📋", "task": "✅",
    "ast": "🌳", "dep_graph": "🕸", "call_chain": "🔗",
    "subagent": "🧠", "mcp": "🔌",
}

PROVIDER_PRESETS = {
    "DeepSeek": {"base_url": "https://api.deepseek.com"},
    "Anthropic Claude": {"base_url": ""},
    "OpenAI": {"base_url": "https://api.openai.com/v1"},
}
PROVIDER_NAMES = list(PROVIDER_PRESETS.keys())


class WebStreamHandler(StreamHandler):
    """StreamHandler 桥接：将 Agent 事件推送到 web_server SSE。"""

    def __init__(self, web_server: WebServer):
        self.web_server = web_server
        self._tool_name = ""

    def on_text(self, text: str) -> None:
        self.web_server.push_sse("text", {"delta": text})

    def on_thinking(self, text: str) -> None:
        self.web_server.push_sse("thought", {"delta": text})

    def on_tool_start(self, name: str, input_data: dict) -> None:
        self._tool_name = name
        self.web_server.push_sse("tool", {"subtype": "start", "tool_name": name})

    def on_tool_result(self, result: str) -> None:
        is_err = any(k in result[:100].lower() for k in ("error", "错误", "失败", "❌"))
        self.web_server.push_sse("tool", {
            "subtype": "result",
            "tool_name": self._tool_name or "",
            "status": "error" if is_err else "done",
        })

    def on_error(self, error: str) -> None:
        self.web_server.push_sse("error", {"message": error})

    def on_turn_plan(self, tool_count: int) -> None:
        pass

    def on_turn_end(self) -> None:
        pass

    def on_complete(self) -> None:
        self.web_server.push_sse("session", {"subtype": "end"})


class AgentApp:
    """AgiCode Web 应用 —— 纯后端，无 GUI。

    管理 Agent 生命周期和配置，通过 WebServer 提供 HTTP API。
    """

    def __init__(self):
        self.agent: Agent | None = None
        self.provider_name: str = "DeepSeek"
        self.api_key: str = ""
        self.model: str = "deepseek-chat"
        self.base_url: str = ""
        self.busy = False
        self._lock = threading.Lock()
        self._think_start: float = 0.0

        # 加载配置
        self._load_config()

        # 启动 Web 服务器（注册路由前设置 agent_app 引用）
        self.web_server = WebServer(agent_app=self)
        port = self.web_server.start()
        url = self.web_server.get_url()

        print(f"\n  AgiCode Web v2.0.0")
        print(f"  Provider: {self.provider_name} / {self.model}")
        print(f"  URL: {url}")
        print(f"  按 Ctrl+C 退出\n")

        webbrowser.open(url)

        # 保持主线程运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.web_server.stop()
            print("再见。")

    def _config_path(self):
        return os.path.join(os.path.dirname(__file__), "..", "config.json")

    def _load_config(self):
        p = self._config_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self.provider_name = d.get("provider", "DeepSeek")
                self.api_key = d.get("api_key", "")
                self.model = d.get("model", "deepseek-chat")
                self.base_url = d.get("base_url", "")
            except Exception:
                pass
        self._init_agent()

    def _save_config(self):
        try:
            with open(self._config_path(), "w", encoding="utf-8") as f:
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
            self.agent = None
            return
        try:
            config = {
                "api_key": self.api_key,
                "model": self.model,
                "base_url": self.base_url,
                "max_tokens": 8192,
                "temperature": 0.0,
                "request_timeout": 120,
            }
            self.agent = Agent(config=config)
        except Exception as e:
            print(f"[AgiCode] 初始化失败: {e}")
            self.agent = None

    def send_text(self, text: str) -> tuple[bool, str]:
        """发送消息给 Agent（线程安全）。

        Returns:
            (success, error_message)
        """
        with self._lock:
            if self.busy:
                return False, "Agent 正在工作中"
            if not self.api_key:
                return False, "请先配置 API Key"
            if not self.agent:
                self._init_agent()
                if not self.agent:
                    return False, "Agent 初始化失败"
            self.busy = True

        self._think_start = time.time()
        self.web_server.push_sse("session", {"subtype": "start"})

        def _run():
            try:
                handler = WebStreamHandler(web_server=self.web_server)
                self.agent.run_iteration(text, handler)
            except Exception as e:
                self.web_server.push_sse("error", {"message": str(e)})
            finally:
                # 思考耗时
                elapsed = time.time() - self._think_start
                if elapsed >= 1.0:
                    unit = "s" if elapsed < 60 else "m"
                    val = elapsed if elapsed < 60 else elapsed / 60
                    self.web_server.push_sse("text", {"delta": f"\n  🧠 思考 {val:.1f}{unit}\n"})
                with self._lock:
                    self.busy = False
                self.web_server.push_sse("session", {"subtype": "end"})

        threading.Thread(target=_run, daemon=True).start()
        return True, ""

    def stop_agent(self):
        """终止当前 Agent 执行。"""
        with self._lock:
            self.busy = False
        self.web_server.push_sse("error", {"message": "⏹ 已终止"})
        self.web_server.push_sse("session", {"subtype": "end"})

    def get_config(self) -> dict:
        return {
            "provider": self.provider_name,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
        }

    def set_config(self, cfg: dict) -> str:
        """设置配置并重新初始化 Agent。

        Returns:
            空字符串表示成功，非空为错误消息。
        """
        self.provider_name = cfg.get("provider", self.provider_name)
        # 避免 "****" 伪装 key 覆盖真实 key
        incoming_key = cfg.get("api_key", "")
        if incoming_key and incoming_key != "****":
            self.api_key = incoming_key
        self.model = cfg.get("model", self.model)
        self.base_url = cfg.get("base_url", self.base_url)
        self._save_config()
        self._init_agent()
        if not self.agent and self.api_key:
            return "Agent 初始化失败，请检查 API Key 和模型名称"
        return ""


def run():
    AgentApp()
