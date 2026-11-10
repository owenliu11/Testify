import os
import time
from collections.abc import Callable
from datetime import datetime

import httpx

API = os.environ.get("API_BASE_URL", "http://127.0.0.1:18000")
FIXTURE = os.environ.get("FIXTURE_URL", "http://127.0.0.1:18080")
BBOX = "37,-123,38.5,-121.5"


def wait_for(check: Callable[[], object], what: str, deadline_s: float = 45) -> object:
    deadline = time.monotonic() + deadline_s
    last = None
    while time.monotonic() < deadline:
        try:
            last = check()
        except httpx.HTTPError as exc:
            last = exc
        else:
            if last:
                return last
        time.sleep(0.25)
    raise AssertionError(f"Timed out waiting for {what}. Last result: {last!r}")


def states_requests() -> int:
    requests = httpx.get(f"{FIXTURE}/requests", timeout=5).json()
    return sum(item["path"] == "/states/all" for item in requests)


def test_int_01_row_reaches_live_and_history() -> None:
    wait_for(
        lambda: httpx.get(f"{API}/health", timeout=5).json().get("status") == "ok",
        "API health status ok",
    )
    before = states_requests()
    previous = httpx.get(f"{API}/aircraft/abc123/track", timeout=5).json()
    previous_times = {point["time"] for point in previous["points"]}
    if previous_times:
        latest = max(datetime.fromisoformat(value).timestamp() for value in previous_times)
        while time.time() < latest + 1:
            time.sleep(0.05)

    cycle = httpx.post(
        f"{API}/__test/ingest/cycles", json={"scenario_id": "normal"}, timeout=30
    ).json()

    assert cycle["status"] == "succeeded", cycle
    assert (cycle["accepted"], cycle["rejected"]) == (1, 0), cycle
    assert states_requests() == before + 1

    def live_aircraft() -> list[dict[str, object]]:
        body = httpx.get(f"{API}/aircraft", params={"bbox": BBOX}, timeout=5).json()
        return [item for item in body["aircraft"] if item["icao24"] == "abc123"]

    aircraft = wait_for(live_aircraft, "abc123 in live state")[0]
    assert aircraft["callsign"] == "TEST123"
    assert aircraft["velocity"] == 250.0

    def track() -> dict[str, object] | None:
        body = httpx.get(f"{API}/aircraft/abc123/track", timeout=5).json()
        return body if any(
            point["time"] not in previous_times and point["latitude"] == 37.6
            for point in body["points"]
        ) else None

    wait_for(track, "a committed abc123 observation")
