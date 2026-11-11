"""Reject a demo failure unless it shows the intended missing leave event."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(sys.argv[1])
files = list(root.glob("*.xml"))
if len(files) != 1:
    raise SystemExit(f"Expected one JUnit result, found {len(files)}")
failure = ET.parse(files[0]).find(".//failure")
if failure is None or "WS-02 missing leave" not in (failure.text or ""):
    raise SystemExit("Failure was not the intended WS-02 missing-leave assertion")
evidence = root / "evidence" / "1"
health = json.loads((evidence / "health.json").read_text())
requests = json.loads((evidence / "fixture_requests.json").read_text())
cycles = [json.loads(line) for line in (evidence / "cycles.jsonl").read_text().splitlines()]
frames = [json.loads(line) for line in (evidence / "ws_frames.jsonl").read_text().splitlines()]
detail = json.loads((evidence / "aircraft_detail.jsonl").read_text().splitlines()[-1])
if health.get("status") != "ok":
    raise SystemExit("API health was not ok; failure could be an unavailable service")
if [cycle.get("scenario_id") for cycle in cycles] != ["stationary", "moved", "outside"]:
    raise SystemExit("Expected three completed fixture cycles")
if any(cycle.get("status") != "succeeded" for cycle in cycles):
    raise SystemExit("A provider cycle failed")
if sum(item.get("path") == "/states/all" for item in requests) != 3:
    raise SystemExit("Expected exactly three provider requests")
if detail["aircraft"]["longitude"] != -120.0:
    raise SystemExit("Aircraft did not move outside the subscribed viewport")
if not any(frame.get("enter") for frame in frames) or not any(frame.get("update") for frame in frames):
    raise SystemExit("Expected enter and update frames before missing leave")
if any("abc123" in frame.get("leave", []) for frame in frames):
    raise SystemExit("Unexpected leave frame appeared")
print("Verified expected failure: healthy API, successful cycles, aircraft outside viewport, no leave frame")
