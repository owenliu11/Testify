"""Seed invented anomaly records only inside the dedicated test database."""

import os
import re
import subprocess

import httpx
import pytest

API = os.getenv("API_BASE_URL", "http://127.0.0.1:18000")


def test_api_10_populated_anomaly_filters():
    project = os.environ.get("TESTFORGE_COMPOSE_PROJECT", "")
    if not re.fullmatch(r"tf_m2_[0-9]+", project):
        pytest.fail("Run this test with scripts/run-skywatch-isolated.sh")
    sql = """
        INSERT INTO anomalies (event_id, icao24, detector, window_start, window_end,
                               detected_at, features, region, is_synthetic)
        VALUES ('m4-real', 'abc123', 'rule:demo', now() - interval '1 minute', now(), now(), '{}', 'test', false),
               ('m4-synthetic', 'abc123', 'rule:demo', now() - interval '2 minutes', now(), now(), '{}', 'test', true),
               ('m4-other', 'def456', 'rule:other', now() - interval '3 minutes', now(), now(), '{}', 'test', false)
    """
    subprocess.run(
        ["docker", "compose", "-p", project, "-f", "targets/skywatch/compose.yaml",
         "exec", "-T", "db", "psql", "-U", "skywatch", "-d", "skywatch", "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True, capture_output=True, text=True, timeout=15,
    )

    def ids(**params):
        response = httpx.get(f"{API}/anomalies", params=params, timeout=5)
        response.raise_for_status()
        return {item["event_id"] for item in response.json()["anomalies"]}

    assert ids(icao24="ABC123", type="demo") == {"m4-real"}
    assert ids(icao24="abc123", type="demo", include_synthetic="true") == {"m4-real", "m4-synthetic"}
    assert ids(type="other") == {"m4-other"}
