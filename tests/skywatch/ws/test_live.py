"""Black-box WebSocket protocol checks against an isolated SkyWatch stack."""

import json
import os
import time
from pathlib import Path

import httpx
from websockets.sync.client import connect

API = os.getenv("API_BASE_URL", "http://127.0.0.1:18000")
FIXTURE = os.getenv("FIXTURE_URL", "http://127.0.0.1:18080")
WS = os.getenv("WS_URL", "ws://127.0.0.1:18000/ws/live")
BBOX = [37, -123, 38.5, -121.5]


def record(name, value):
    directory = os.getenv("TESTFORGE_EVIDENCE_DIR")
    if directory:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        with (path / name).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value) + "\n")


def cycle(scenario):
    httpx.post(f"{FIXTURE}/scenario", json={"scenario": scenario}, timeout=5).raise_for_status()
    response = httpx.post(f"{API}/__test/ingest/cycles", json={"scenario_id": scenario}, timeout=30)
    response.raise_for_status()
    record("cycles.jsonl", response.json())
    assert response.json()["status"] == "succeeded", response.text
    return response.json()


def receive(ws, condition, timeout=10, what="expected frame"):
    deadline = time.monotonic() + timeout
    frames = []
    while time.monotonic() < deadline:
        try:
            frame = json.loads(ws.recv(timeout=max(0.01, deadline - time.monotonic())))
        except TimeoutError:
            break
        frames.append(frame)
        record("ws_frames.jsonl", frame)
        if condition(frame):
            return frame
    raise AssertionError(f"{what}: WebSocket frame not received; observed: {frames!r}")


def subscribe(ws):
    ws.send(json.dumps({"t": "viewport", "bbox": BBOX}))
    return receive(ws, lambda frame: frame["t"] == "snapshot")


def rows(frame, key):
    return [dict(zip(frame["fields"], row, strict=True)) for row in frame[key]]


def test_ws_01_snapshot_has_expected_fields_and_aircraft():
    cycle("stationary")
    with connect(WS, open_timeout=5) as ws:
        frame = subscribe(ws)
        assert isinstance(frame["seq"], int) and isinstance(frame["server_time"], (int, float))
        aircraft = rows(frame, "aircraft")
        assert len(aircraft) == 1
        assert aircraft[0]["icao24"] == "abc123"
        assert aircraft[0]["callsign"] == "TEST123"
        assert aircraft[0]["velocity"] == 0


def test_ws_02_enter_update_and_leave():
    with connect(WS, open_timeout=5) as ws:
        snapshot = subscribe(ws)
        assert snapshot["aircraft"] == []
        cycle("stationary")
        enter = receive(ws, lambda f: f["t"] == "delta" and bool(f["enter"]))
        assert enter["enter"][0][0] == "abc123"
        # The provider timestamp has one-second precision.
        first_contact = enter["enter"][0][9]
        while time.time() < first_contact + 1:
            time.sleep(0.05)
        cycle("moved")
        update = receive(ws, lambda f: f["t"] == "delta" and bool(f["update"]))
        assert update["update"][0][0] == "abc123"
        assert update["update"][0][2] == -122.2
        while time.time() < update["update"][0][9] + 1:
            time.sleep(0.05)
        cycle("outside")
        detail = httpx.get(f"{API}/aircraft/abc123", timeout=5)
        detail.raise_for_status()
        record("aircraft_detail.jsonl", detail.json())
        assert detail.json()["aircraft"]["longitude"] == -120.0
        leave = receive(ws, lambda f: f["t"] == "delta" and "abc123" in f["leave"], what="WS-02 missing leave")
        assert snapshot["seq"] < enter["seq"] < update["seq"] < leave["seq"]


def test_ws_03_reconnect_gets_fresh_snapshot():
    cycle("stationary")
    with connect(WS, open_timeout=5) as first:
        assert rows(subscribe(first), "aircraft")[0]["icao24"] == "abc123"
    with connect(WS, open_timeout=5) as second:
        assert rows(subscribe(second), "aircraft")[0]["icao24"] == "abc123"


def test_ws_04_stale_aircraft_eviction_emits_leave():
    with connect(WS, open_timeout=5) as ws:
        subscribe(ws)
        cycle("old")
        receive(ws, lambda f: f["t"] == "delta" and bool(f["enter"]), timeout=5)
        frame = receive(ws, lambda f: f["t"] == "delta" and "abc123" in f["leave"], timeout=10)
        assert frame["leave"] == ["abc123"]
