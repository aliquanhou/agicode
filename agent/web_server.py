"""web_server — FastAPI 本地服务器，为 Monaco Editor 提供后端服务。

启动时绑定随机端口，通过 SSE 推送流式事件，提供 REST API。
在守护线程中运行 uvicorn，与 customtkinter GUI 共存。
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# ── 前端静态文件目录 ──
EDITOR_DIR = Path(__file__).parent / "editor"


# ── 请求模型 ──

class SendBody(BaseModel):
    text: str


class DiffBody(BaseModel):
    diff: str


# ── Unified Diff 解析 ──

def parse_unified_diff(diff_text: str) -> dict:
    """解析 Unified Diff 文本，返回 original 和 modified 内容。

    Args:
        diff_text: 完整的 unified diff 字符串（含 ---/+++ 头）

    Returns:
        {"original": str, "modified": str}
    """
    original_lines: list[str] = []
    modified_lines: list[str] = []

    for line in diff_text.split("\n"):
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@ "):
            continue
        if line.startswith("\\ "):  # No newline at end of file
            continue
        if line.startswith("-"):
            original_lines.append(line[1:])
        elif line.startswith("+"):
            modified_lines.append(line[1:])
        else:
            original_lines.append(line[1:] if line.startswith(" ") else line)
            modified_lines.append(line[1:] if line.startswith(" ") else line)

    return {
        "original": "\n".join(original_lines),
        "modified": "\n".join(modified_lines),
    }


# ── WebServer ──

class WebServer:
    """FastAPI 本地服务器 —— 为 Monaco Editor 提供后端 API 和静态文件服务。

    用法:
        server = WebServer(agent_app)
        port = server.start()
        print(server.get_url())
        # ...
        server.stop()
    """

    def __init__(self, agent_app=None):
        self.agent_app = agent_app
        self.port: int = 0
        self.host: str = "127.0.0.1"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._sse_clients: list[asyncio.Queue] = []
        self._sse_lock = threading.Lock()

        self.app = FastAPI(title="AgiCode Monaco Server")
        self._register_routes()

    def _register_routes(self):
        app = self.app

        # ── 静态文件 ──

        @app.get("/")
        async def serve_index():
            """提供 Monaco Editor 主页面。"""
            index_path = EDITOR_DIR / "index.html"
            if not index_path.exists():
                return HTMLResponse("<h1>AgiCode Editor</h1><p>index.html not found.</p>", status_code=404)
            return FileResponse(str(index_path))

        @app.get("/{filename:path}")
        async def serve_static(filename: str):
            """提供 editor/ 目录下的静态文件。"""
            # 安全路径检查
            file_path = EDITOR_DIR / filename
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(EDITOR_DIR.resolve())):
                return HTMLResponse("Forbidden", status_code=403)
            if not file_path.exists() or not file_path.is_file():
                return HTMLResponse("Not Found", status_code=404)
            return FileResponse(str(file_path))

        # ── SSE 流式输出 ──

        @app.get("/api/stream")
        async def sse_stream(request: Request):
            """SSE 端点：推送流式文本事件给前端 Monaco Editor。"""
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
                            yield f": keepalive\n\n"
                            continue
                        if data is None:  # 关闭信号
                            yield f"event: close\ndata: \n\n"
                            break
                        event_type = data.get("type", "message")
                        payload = json.dumps(data.get("payload", {}))
                        yield f"event: {event_type}\ndata: {payload}\n\n"
                finally:
                    with self._sse_lock:
                        if queue in self._sse_clients:
                            self._sse_clients.remove(queue)

            return EventSourceResponse(event_generator())

        # ── REST API ──

        @app.post("/api/send")
        async def api_send(body: SendBody):
            """接收用户消息并转发给 Agent。"""
            if not self.agent_app:
                return {"status": "error", "message": "Agent not initialized"}
            text = body.text
            if not text.strip():
                return {"status": "error", "message": "Empty message"}
            # 在主线程中发送（线程安全）
            if hasattr(self.agent_app, '_send_text'):
                self.agent_app.after_idle(lambda: self.agent_app._send_text(text))
            return {"status": "ok"}

        @app.post("/api/diff")
        async def api_diff(body: DiffBody):
            """解析 Unified Diff 并返回 original/modified 内容。"""
            try:
                result = parse_unified_diff(body.diff)
                return {"status": "ok", **result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @app.get("/api/context")
        async def api_context():
            """返回当前上下文/状态信息。"""
            if not self.agent_app or not self.agent_app.agent:
                return {"busy": False, "provider": "", "model": "", "workflow": {}}
            agent = self.agent_app.agent
            workflow = agent.workflow.to_dict() if agent.workflow else {}
            return {
                "busy": self.agent_app.busy,
                "provider": self.agent_app.provider_name,
                "model": self.agent_app.model,
                "workflow": workflow,
            }

        @app.get("/api/history")
        async def api_history():
            """返回对话历史。"""
            if not self.agent_app or not self.agent_app.agent:
                return {"messages": []}
            return {"messages": self.agent_app.agent.messages}

        @app.get("/api/health")
        async def api_health():
            return {"status": "ok", "port": self.port}

    # ── 生命周期 ──

    def start(self) -> int:
        """在随机端口上以守护线程启动 uvicorn。

        Returns:
            绑定的端口号
        """
        self.port = _find_free_port()
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config=config)
        self._thread = threading.Thread(
            target=self._server.run,
            daemon=True,
            name="agicode-web-server",
        )
        self._thread.start()
        return self.port

    def stop(self):
        """优雅关闭服务器。"""
        # 通知所有 SSE 客户端断开
        with self._sse_lock:
            for queue in self._sse_clients:
                try:
                    queue.put_nowait(None)
                except Exception:
                    pass
            self._sse_clients.clear()
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)

    def get_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # ── SSE 推送 ──

    def push_sse(self, event_type: str, payload: Any):
        """广播事件给所有连接的 SSE 客户端。

        Args:
            event_type: 事件类型（text, tool_start, tool_result 等）
            payload: 事件负载（dict）
        """
        with self._sse_lock:
            for queue in self._sse_clients:
                try:
                    queue.put_nowait({"type": event_type, "payload": payload})
                except asyncio.QueueFull:
                    pass


# ── 工具函数 ──

def _find_free_port() -> int:
    """查找系统空闲端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
