"""Local-only read-only teaching slice. No authentication, database or model."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ASSETS = Path(__file__).resolve().parent
DOCUMENTS = [
    {"id": "policy-1", "title": "虚构采购资料清单", "version": "1",
     "text": "教学规则：材料包括项目说明与供应商资料。"},
    {"id": "policy-2", "title": "虚构制度更新说明", "version": "2",
     "text": "教学规则：查询结果应展示来源版本。"},
]


def search(query: str) -> list[dict[str, str]]:
    term = query.casefold()
    return [dict(doc) for doc in DOCUMENTS
            if term in (doc["title"] + doc["text"]).casefold()]


class Handler(BaseHTTPRequestHandler):
    def respond(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Client stopped waiting; this slice has no write side effect.

    def as_json(self, status: int, value: dict) -> None:
        self.respond(status, json.dumps(value, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if len(self.path) > 2048:
            self.as_json(414, {"error": "请求地址过长"})
            return
        target = urlsplit(self.path)
        if target.path == "/api/search":
            try:
                parameters = parse_qs(target.query, keep_blank_values=True,
                                      max_num_fields=10)
            except ValueError:
                self.as_json(400, {"error": "查询参数无效"})
                return
            values = parameters.get("q", [])
            if len(values) != 1 or not 1 <= len(values[0].strip()) <= 80:
                self.as_json(400, {"error": "请输入1至80个字符"})
                return
            self.as_json(200, {"items": search(values[0].strip()),
                               "mode": "fictional-read-only-demo"})
            return
        routes = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        if target.path not in routes:
            self.as_json(404, {"error": "路径不存在"})
            return
        filename, content_type = routes[target.path]
        self.respond(200, (ASSETS / filename).read_bytes(), content_type)

    def log_message(self, format: str, *args: object) -> None:
        pass  # Avoid recording query strings in this teaching example.


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.daemon_threads = True
        print(f"Local lesson: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
