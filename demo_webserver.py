"""
demo_webserver.py — 简易 HTTP API 服务器
功能：提供 RESTful API，返回系统信息
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import platform
import psutil
import datetime


class APIHandler(BaseHTTPRequestHandler):
    """处理 HTTP 请求"""

    def do_GET(self):
        if self.path == "/":
            self._send_json({
                "service": "AgiCode Demo API",
                "version": "1.0",
                "endpoints": {
                    "/": "此信息",
                    "/system": "系统信息",
                    "/processes": "进程列表（前10）",
                    "/time": "当前时间"
                }
            })
        elif self.path == "/system":
            self._send_json({
                "system": platform.system(),
                "node": platform.node(),
                "release": platform.release(),
                "processor": platform.processor(),
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory": {
                    "total_gb": round(psutil.virtual_memory().total / 1024**3, 2),
                    "available_gb": round(psutil.virtual_memory().available / 1024**3, 2),
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total_gb": round(psutil.disk_usage("/").total / 1024**3, 2),
                    "free_gb": round(psutil.disk_usage("/").free / 1024**3, 2),
                    "percent": psutil.disk_usage("/").percent
                }
            })
        elif self.path == "/processes":
            processes = []
            for proc in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                              key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:10]:
                processes.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "cpu": proc.info["cpu_percent"],
                    "memory": round(proc.info["memory_percent"] or 0, 2)
                })
            self._send_json({"processes": processes, "count": len(processes)})
        elif self.path == "/time":
            self._send_json({
                "now": datetime.datetime.now().isoformat(),
                "timezone": time.tzname
            })
        else:
            self._send_json({"error": "Not Found"}, 404)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())

    def log_message(self, format, *args):
        print(f"[API] {self.client_address[0]} - {format % args}")


import time

if __name__ == "__main__":
    port = 8888
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print(f"🚀 AgiCode Demo API 运行在 http://localhost:{port}")
    print(f"   试试: http://localhost:{port}/system")
    print(f"   试试: http://localhost:{port}/processes")
    print("   按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()
