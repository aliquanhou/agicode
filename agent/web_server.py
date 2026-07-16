"""web_server — FastAPI 本地服务器，网页版 AgiCode 后端。

启动时绑定随机端口，通过 SSE 推送流式事件，提供 REST API。
在守护线程中运行 uvicorn。
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Body, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse


EDITOR_DIR = Path(__file__).parent / "editor"


class SendBody(BaseModel):
    text: str


def parse_unified_diff(diff_text: str) -> dict:
    """解析 Unified Diff 文本，返回 original 和 modified 内容。"""
    original_lines: list[str] = []
    modified_lines: list[str] = []
    for line in diff_text.split("\n"):
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@ "):
            continue
        if line.startswith("\\ "):
            continue
        if line.startswith("-"):
            original_lines.append(line[1:])
        elif line.startswith("+"):
            modified_lines.append(line[1:])
        else:
            ctx = line[1:] if line.startswith(" ") else line
            original_lines.append(ctx)
            modified_lines.append(ctx)
    return {"original": "\n".join(original_lines), "modified": "\n".join(modified_lines)}


class WebServer:
    """FastAPI 本地服务器 —— 网页版 AgiCode 后端。

    通过 SSE 推送 Agent 事件到浏览器，通过 REST API 接收用户输入。
    """

    def __init__(self, agent_app=None):
        self.agent_app = agent_app
        self.port: int = 0
        self.host: str = "127.0.0.1"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._sse_clients: list[asyncio.Queue] = []
        self._sse_lock = threading.Lock()

        self.app = FastAPI(title="AgiCode Web")
        self._register_routes()

    def _register_routes(self):
        app = self.app

        # ══ 首页 ══

        @app.get("/")
        async def serve_index():
            """提供主页面。"""
            index_path = EDITOR_DIR / "index.html"
            if not index_path.exists():
                return HTMLResponse("<h1>AgiCode</h1><p>Frontend not found.</p>", status_code=404)
            return FileResponse(str(index_path))

        # ══ SSE 流式输出 ══

        @app.get("/api/stream")
        async def sse_stream(request: Request):
            """SSE 端点：推送 Agent 事件给前端。"""
            queue: asyncio.Queue = asyncio.Queue()
            with self._sse_lock:
                self._sse_clients.append(queue)

            async def event_generator():
                try:
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            data = await asyncio.wait_for(queue.get(), timeout=30.0)
                        except asyncio.TimeoutError:
                            yield ": keepalive\n\n"
                            continue
                        if data is None:
                            break
                        event_type = data.get("type", "message")
                        payload = json.dumps(data.get("payload", {}))
                        yield f"event: {event_type}\ndata: {payload}\n\n"
                finally:
                    with self._sse_lock:
                        if queue in self._sse_clients:
                            self._sse_clients.remove(queue)

            return EventSourceResponse(event_generator())

        # ══ REST API ══

        @app.post("/api/send")
        async def api_send(body: SendBody):
            """发送用户消息给 Agent。"""
            if not self.agent_app:
                return {"status": "error", "message": "Agent not initialized"}
            if not self.agent_app.api_key:
                return {"status": "error", "message": "请先点击 ⚙ Settings 配置 API Key"}
            if self.agent_app.busy:
                return {"status": "error", "message": "Agent 正在工作中，请等待完成"}
            text = body.text.strip()
            if not text:
                return {"status": "error", "message": "消息不能为空"}
            if hasattr(self.agent_app, '_send_text'):
                self.agent_app.after_idle(lambda: self.agent_app._send_text(text))
            return {"status": "ok"}

        @app.post("/api/stop")
        async def api_stop():
            """终止当前 Agent 执行。"""
            if self.agent_app and hasattr(self.agent_app, '_stop_agent'):
                self.agent_app.after_idle(self.agent_app._stop_agent)
            return {"status": "ok"}

        @app.post("/api/clear")
        async def api_clear():
            """清空对话。"""
            if self.agent_app and hasattr(self.agent_app, '_clear_chat'):
                self.agent_app.after_idle(self.agent_app._clear_chat)
            return {"status": "ok"}

        @app.post("/api/retry")
        async def api_retry():
            """重试上次输入。"""
            if self.agent_app and hasattr(self.agent_app, '_retry_last'):
                self.agent_app.after_idle(self.agent_app._retry_last)
            return {"status": "ok"}

        @app.post("/api/diff")
        async def api_diff(body: dict):
            """解析 Unified Diff。"""
            try:
                result = parse_unified_diff(body.get("diff", ""))
                return {"status": "ok", **result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @app.get("/api/context")
        async def api_context():
            """返回上下文信息。"""
            if not self.agent_app:
                return {"busy": False, "provider": "", "model": "", "has_key": False}
            return {
                "busy": self.agent_app.busy,
                "provider": self.agent_app.provider_name,
                "model": self.agent_app.model,
                "has_key": bool(self.agent_app.api_key),
            }

        @app.get("/api/config")
        async def api_get_config():
            """获取当前配置。"""
            if not self.agent_app:
                return {"provider": "", "model": "", "api_key": "", "base_url": ""}
            return {
                "provider": self.agent_app.provider_name,
                "model": self.agent_app.model,
                "api_key": "****" if self.agent_app.api_key else "",
                "base_url": self.agent_app.base_url,
            }

        @app.post("/api/config")
        async def api_set_config(body: dict):
            """保存配置并重新初始化 Agent。"""
            if not self.agent_app:
                return {"status": "error", "message": "Not initialized"}
            try:
                self.agent_app.provider_name = body.get("provider", self.agent_app.provider_name)
                self.agent_app.api_key = body.get("api_key", self.agent_app.api_key)
                self.agent_app.model = body.get("model", self.agent_app.model)
                self.agent_app.base_url = body.get("base_url", self.agent_app.base_url)
                self.agent_app._save_config()
                self.agent_app._init_agent()
                return {"status": "ok"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @app.get("/api/tools")
        async def api_tools():
            """返回工具状态。"""
            if not self.agent_app:
                return {"tools": {}}
            return {"tools": getattr(self.agent_app, 'tool_status', {})}

        @app.get("/api/health")
        async def api_health():
            return {"status": "ok", "port": self.port}

        # ══ 静态文件（catch-all，必须在 API 路由之后）══

        @app.get("/{filename:path}")
        async def serve_static(filename: str):
            """提供 editor/ 下的静态文件。"""
            file_path = (EDITOR_DIR / filename).resolve()
            if not str(file_path).startswith(str(EDITOR_DIR.resolve())):
                return HTMLResponse("Forbidden", status_code=403)
            if not file_path.exists() or not file_path.is_file():
                return HTMLResponse("Not Found", status_code=404)
            return FileResponse(str(file_path))

    # ── 生命周期 ──

    def start(self) -> int:
        """在随机端口上以守护线程启动 uvicorn。"""
        self.port = _find_free_port()
        config = uvicorn.Config(
            self.app, host=self.host, port=self.port,
            log_level="warning", access_log=False,
        )
        self._server = uvicorn.Server(config=config)
        self._thread = threading.Thread(
            target=self._server.run, daemon=True,
            name="agicode-web-server",
        )
        self._thread.start()
        return self.port

    def stop(self):
        """关闭服务器。"""
        with self._sse_lock:
            for q in self._sse_clients:
                try: q.put_nowait(None)
                except: pass
            self._sse_clients.clear()
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)

    def get_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def push_sse(self, event_type: str, payload: Any):
        """广播事件到所有 SSE 客户端。"""
        with self._sse_lock:
            for q in self._sse_clients:
                try:
                    q.put_nowait({"type": event_type, "payload": payload})
                except asyncio.QueueFull:
                    pass


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
