"""web_server — FastAPI 本地服务器，网页版 AgiCode 后端。

启动时绑定随机端口，通过 SSE 推送流式事件，提供 REST API。
在守护线程中运行 uvicorn。
"""

from __future__ import annotations

import asyncio
import json
import os
import queue as q_module
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
        # 使用 threading.Queue（线程安全，Agent 后台线程可写入）
        self._sse_queues: list[q_module.Queue] = []
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
            # threading.Queue 是线程安全的，Agent 后台线程可写入
            queue: q_module.Queue = q_module.Queue(maxsize=1000)
            with self._sse_lock:
                self._sse_queues.append(queue)

            async def event_generator():
                loop = asyncio.get_event_loop()
                try:
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            data = await loop.run_in_executor(
                                None, lambda: queue.get(timeout=0.5)
                            )
                        except q_module.Empty:
                            yield {"event": "ping", "data": json.dumps({"type": "keepalive"})}
                            continue
                        except Exception:
                            break
                        if data is None:
                            break
                        event_type = data.get("type", "message")
                        payload = data.get("payload", {})
                        # 序列化为 JSON 字符串，确保前端 JSON.parse 能解析
                        yield {"event": event_type, "data": json.dumps(payload, ensure_ascii=False)}
                finally:
                    with self._sse_lock:
                        if queue in self._sse_queues:
                            self._sse_queues.remove(queue)

            return EventSourceResponse(event_generator())

        # ══ REST API ══

        @app.post("/api/send")
        async def api_send(body: SendBody):
            """发送用户消息给 Agent。"""
            if not self.agent_app:
                return {"status": "error", "message": "Agent not initialized"}
            if not self.agent_app.api_key:
                return {"status": "error", "message": "请先配置 API Key（点击右上角 ⚙ Settings）"}
            if self.agent_app.busy:
                return {"status": "error", "message": "Agent 正在工作中，请等待完成"}
            text = body.text.strip()
            if not text:
                return {"status": "error", "message": "消息不能为空"}
            success, err = self.agent_app.send_text(text)
            if success:
                return {"status": "ok"}
            return {"status": "error", "message": err}

        @app.post("/api/stop")
        async def api_stop():
            """终止当前 Agent 执行。"""
            if self.agent_app:
                self.agent_app.stop_agent()
            return {"status": "ok"}

        @app.post("/api/clear")
        async def api_clear():
            """清空对话（由前端处理）。"""
            return {"status": "ok"}

        @app.post("/api/retry")
        async def api_retry():
            """重试上次输入（由前端处理）。"""
            return {"status": "ok"}

        @app.post("/api/diff")
        async def api_diff(body: dict = Body(...)):
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
            cfg = self.agent_app.get_config()
            return {
                "provider": cfg["provider"],
                "model": cfg["model"],
                "api_key": "****" if cfg["api_key"] else "",
                "base_url": cfg["base_url"],
            }

        @app.post("/api/config")
        async def api_set_config(body: dict = Body(...)):
            """保存配置并重新初始化 Agent。"""
            if not self.agent_app:
                return {"status": "error", "message": "Not initialized"}
            err = self.agent_app.set_config(body)
            if err:
                return {"status": "error", "message": err}
            return {"status": "ok"}

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
            for q in self._sse_queues:
                try: q.put_nowait(None)
                except: pass
            self._sse_queues.clear()
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)

    def get_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def push_sse(self, event_type: str, payload: Any):
        """广播事件到所有 SSE 客户端（线程安全）。"""
        with self._sse_lock:
            for q in self._sse_queues:
                try:
                    q.put_nowait({"type": event_type, "payload": payload})
                except q_module.Full:
                    pass


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
