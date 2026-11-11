"""Regressions for INT-07 and INT-08; each needs its own fresh stack."""

import os
import time

import httpx
from websockets.sync.client import connect

from testforge.wait import wait_for

API = os.getenv("API_BASE_URL", "http://127.0.0.1:18000")
FIXTURE = os.getenv("FIXTURE_URL", "http://127.0.0.1:18080")
WS = os.getenv("WS_URL", "ws://127.0.0.1:18000/ws/live")


def test_int_07_invalid_last_contact_does_not_kill_broadcast():
    httpx.post(f"{FIXTURE}/scenario", json={"scenario": "bad_contact"}, timeout=5).raise_for_status()
    cycle = httpx.post(f"{API}/__test/ingest/cycles", json={"scenario_id": "bad_contact"}, timeout=30).json()
    assert cycle["status"] in {"succeeded", "failed"}
    time.sleep(2)  # Allow the broadcast tick that triggers the original defect.
    with connect(WS, open_timeout=5) as ws:
        ws.send('{"t":"viewport","bbox":[37,-123,38.5,-121.5]}')
        message = ws.recv(timeout=5)
        assert '"snapshot"' in message, message


def test_int_08_invalid_snapshot_does_not_kill_continuous_polling():
    # Start the fixture with FIXTURE_SCENARIO=bad_snapshot and test mode disabled.
    def requests():
        response = httpx.get(f"{FIXTURE}/requests", timeout=5)
        response.raise_for_status()
        return [r for r in response.json() if r["path"] == "/states/all"]
    wait_for(lambda: len(requests()) >= 2, "a second provider poll after invalid snapshot", deadline_s=50, interval_s=0.5)
