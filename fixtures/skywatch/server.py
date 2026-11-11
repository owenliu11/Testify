"""Synthetic OpenSky stand-in. All aircraft data is invented."""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

REQUESTS: list[dict[str, object]] = []
LOCK = threading.Lock()
SCENARIO = os.getenv("FIXTURE_SCENARIO", "normal")
CALLS = 0
FIXED_TIME = 0
SCENARIOS = {"normal", "nullable", "duplicate", "older", "empty_null", "empty_list", "mixed", "error", "invalid_json", "unauthorized_once", "bad_contact", "bad_snapshot", "old"}


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
        global SCENARIO, CALLS, FIXED_TIME
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if urlsplit(self.path).path == "/token":
            with LOCK:
                REQUESTS.append({"method": "POST", "path": "/token", "scenario": SCENARIO})
            self.send_json({"access_token": "dummy", "expires_in": 3600})
        elif urlsplit(self.path).path == "/scenario":
            try:
                scenario = json.loads(raw)["scenario"]
                if scenario not in SCENARIOS:
                    raise ValueError("unknown scenario")
            except (ValueError, KeyError, TypeError):
                self.send_error(400)
                return
            with LOCK:
                SCENARIO, CALLS, FIXED_TIME = scenario, 0, int(time.time())
            self.send_json({"scenario": scenario})
        else:
            self.send_error(404)

    def do_GET(self) -> None:
        global CALLS
        path = urlsplit(self.path).path
        if path == "/requests":
            with LOCK:
                requests = list(REQUESTS)
            self.send_json(requests)
        elif path == "/states/all":
            with LOCK:
                scenario = SCENARIO
                CALLS += 1
                call = CALLS
                fixed_time = FIXED_TIME
                REQUESTS.append({"method": "GET", "path": path, "scenario": scenario, "query": parse_qs(urlsplit(self.path).query)})
            if scenario == "error" or (scenario == "unauthorized_once" and call == 1):
                self.send_error(503 if scenario == "error" else 401)
                return
            if scenario == "invalid_json":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{invalid")
                return
            now = int(time.time())
            observed = fixed_time if scenario == "duplicate" else now - 58 if scenario == "old" else now - 10 if scenario == "older" else now
            row = state_row(observed)
            if scenario == "older":
                row[9] = 99.0
            if scenario == "nullable":
                row[1] = row[7] = row[9] = None
            if scenario == "bad_contact":
                row[4] = 10**14
            states = None if scenario == "empty_null" else [] if scenario == "empty_list" else [row]
            if scenario == "mixed":
                states.append(["bad"])
            self.send_json({"time": 10**14 if scenario == "bad_snapshot" else now, "states": states})
        else:
            self.send_error(404)

    def log_message(self, *args: object) -> None:
        pass


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
