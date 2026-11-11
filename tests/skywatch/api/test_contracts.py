import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from jsonschema import ValidationError, validate
from testforge.wait import wait_for

API = os.getenv("API_BASE_URL", "http://127.0.0.1:18000")
FIXTURE = os.getenv("FIXTURE_URL", "http://127.0.0.1:18080")
SCHEMA = Path(__file__).parents[3] / "targets/skywatch/contracts/aircraft.schema.json"


def test_api_00_schema_rejects_malformed_response():
    with pytest.raises(ValidationError):
        validate({"as_of": "now", "count": "one", "truncated": False, "aircraft": []}, json.loads(SCHEMA.read_text()))


def test_api_01_health_body():
    response = httpx.get(f"{API}/health", timeout=5)
    response.raise_for_status()
    assert response.json()["status"] == "ok"
    assert response.json()["database"] is True and response.json()["redis"] is True


def test_api_02_collection_contract():
    response = httpx.get(f"{API}/aircraft", params={"bbox": "37,-123,38.5,-121.5"}, timeout=5)
    response.raise_for_status()
    body = response.json()
    validate(body, json.loads(SCHEMA.read_text()))
    assert isinstance(body["aircraft"], list) and isinstance(body["count"], int)
    assert isinstance(body["truncated"], bool) and isinstance(body["as_of"], str)
    assert body["count"] == len(body["aircraft"])
    assert [x["icao24"] for x in body["aircraft"]] == sorted(x["icao24"] for x in body["aircraft"])


@pytest.mark.parametrize("bbox", ["bad", "38,-123,37,-121", "-90,-180,90,180", "0,170,1,-170"])
def test_api_03_invalid_bbox(bbox):
    assert httpx.get(f"{API}/aircraft", params={"bbox": bbox}, timeout=5).status_code == 422


def test_api_04_missing_aircraft():
    assert httpx.get(f"{API}/aircraft/ffffff", timeout=5).status_code == 404


def test_api_05_track_limits():
    for limit in (0, 20001):
        assert httpx.get(f"{API}/aircraft/abc123/track", params={"limit": limit}, timeout=5).status_code == 422


def test_api_06_track_shape():
    response = httpx.get(f"{API}/aircraft/abc123/track", timeout=5)
    response.raise_for_status()
    body = response.json()
    assert {"since", "until", "count", "limit", "truncated", "window_clamped", "points"} <= body.keys()
    assert body["count"] == len(body["points"])


def test_api_07_anomaly_limit_validation():
    assert httpx.get(f"{API}/anomalies", params={"limit": 0}, timeout=5).status_code == 422


def test_api_08_anomaly_filter_shape():
    response = httpx.get(f"{API}/anomalies", params={"icao24": "abc123", "include_synthetic": "false"}, timeout=5)
    response.raise_for_status()
    assert isinstance(response.json(), dict)


def test_api_09_detail_nullable_values_and_track_boundaries():
    httpx.post(f"{FIXTURE}/scenario", json={"scenario": "nullable"}, timeout=5).raise_for_status()
    try:
        result = httpx.post(f"{API}/__test/ingest/cycles", json={"scenario_id": "nullable"}, timeout=30).json()
        assert result["status"] == "succeeded" and result["accepted"] == 1
        def detail():
            response = httpx.get(f"{API}/aircraft/ABC123", timeout=5)
            return response.json() if response.status_code == 200 else None
        aircraft = wait_for(detail, "nullable aircraft detail")
        assert aircraft["aircraft"]["icao24"] == "abc123"
        assert aircraft["aircraft"]["callsign"] is None
        assert aircraft["aircraft"]["velocity"] is None
        def track():
            return httpx.get(f"{API}/aircraft/abc123/track", timeout=5).json()
        body = wait_for(lambda: (value if (value := track())["count"] else None), "nullable track")
        point = body["points"][0]
        assert point["velocity"] is None and point["baro_altitude"] is None
        instant = datetime.fromisoformat(point["time"])
        since = instant - timedelta(seconds=1)
        excluded = httpx.get(f"{API}/aircraft/abc123/track", params={"since": since.isoformat(), "until": instant.isoformat()}, timeout=5).json()
        assert all(p["time"] != point["time"] for p in excluded["points"])
        included = httpx.get(f"{API}/aircraft/abc123/track", params={"since": instant.isoformat(), "until": (instant + timedelta(seconds=1)).isoformat()}, timeout=5).json()
        assert any(p["time"] == point["time"] for p in included["points"])
        assert httpx.get(f"{API}/aircraft/abc123/track", params={"since": instant.isoformat(), "until": instant.isoformat()}, timeout=5).status_code == 422
        wait_for(lambda: time.time() >= instant.timestamp() + 1, "next observation second", deadline_s=3)
        assert httpx.post(f"{API}/__test/ingest/cycles", json={"scenario_id": "nullable"}, timeout=30).json()["accepted"] == 1
        wait_for(lambda: track()["count"] >= 2, "second track observation")
        limited = httpx.get(f"{API}/aircraft/abc123/track", params={"limit": 1}, timeout=5).json()
        assert limited["count"] == 1 and limited["truncated"] is True
    finally:
        httpx.post(f"{FIXTURE}/scenario", json={"scenario": "normal"}, timeout=5).raise_for_status()
