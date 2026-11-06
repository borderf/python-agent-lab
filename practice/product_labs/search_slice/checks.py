"""Exercise actual HTTP routes; does not verify browser interaction or layout."""

from http.server import ThreadingHTTPServer
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler

from server import Handler


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener(ProxyHandler({}))

    def request(path: str) -> tuple[int, bytes, object]:
        try:
            response = opener.open(origin + path, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    try:
        code, body, headers = request("/")
        assert code == 200 and b'<html lang="zh-CN">' in body
        assert headers["X-Content-Type-Options"] == "nosniff"
        for asset in ("/app.js", "/style.css"):
            assert request(asset)[0] == 200
        code, body, _ = request("/api/search?" + urlencode({"q": "采购"}))
        assert code == 200 and len(json.loads(body)["items"]) == 1
        code, body, _ = request("/api/search?q=no-such-document")
        assert code == 200 and json.loads(body)["items"] == []
        for query in ("", "q=", "q=%20", "q=a&q=b", "q=" + "x" * 81):
            code, body, _ = request("/api/search?" + query)
            assert code == 400 and "error" in json.loads(body)
        assert request("/api/search?q=" + "x" * 2050)[0] == 414
        for path in ("/missing", "/../server.py", "/%2e%2e/server.py"):
            assert request(path)[0] == 404
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
    assert not worker.is_alive()
    print("PASS: assets, search, empty results, validation, path boundary, shutdown")
    print("Not covered: browser rendering, login, persistence, model, production")


if __name__ == "__main__":
    main()
