"""Synthetic OpenSky stand-in. All aircraft data is invented."""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

REQUESTS: list[dict[str, str]] = []


def state_row(now: int) -> list[object]:
    return [
        "abc123", "TEST123 ", "Testland", now, now, -122.3, 37.6, 10000.0,
        False, 250.0, 180.0, -2.5, None, 10200.0, "1200", False, 0, 3,
    ]


class Handler(BaseHTTPRequestHandler):
    def send_json(self, body: object) -> None:
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if urlsplit(self.path).path == "/token":
            REQUESTS.append({"method": "POST", "path": "/token"})
            self.send_json({"access_token": "dummy", "expires_in": 3600})
        else:
            self.send_error(404)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/requests":
            self.send_json(REQUESTS)
        elif path == "/states/all":
            REQUESTS.append({"method": "GET", "path": path})
            now = int(time.time())
            self.send_json({"time": now, "states": [state_row(now)]})
        else:
            self.send_error(404)

    def log_message(self, *args: object) -> None:
        pass


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
