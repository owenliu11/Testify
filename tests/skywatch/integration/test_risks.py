"""Serial scenarios; run with a fresh dedicated Compose project per test group."""

import os

import httpx
import pytest

from testforge.wait import wait_for

API = os.getenv("API_BASE_URL", "http://127.0.0.1:18000")
FIXTURE = os.getenv("FIXTURE_URL", "http://127.0.0.1:18080")
BBOX = "37,-123,38.5,-121.5"


@pytest.fixture(autouse=True)
def restore_scenario():
    yield
    httpx.post(f"{FIXTURE}/scenario", json={"scenario": "normal"}, timeout=5).raise_for_status()


def select(scenario):
    response = httpx.post(f"{FIXTURE}/scenario", json={"scenario": scenario}, timeout=5)
    response.raise_for_status()


def cycle(scenario):
    response = httpx.post(f"{API}/__test/ingest/cycles", json={"scenario_id": scenario}, timeout=30)
    response.raise_for_status()
    body = response.json()
    saved = httpx.get(f"{API}/__test/ingest/cycles/{body['cycle_id']}", timeout=5)
    saved.raise_for_status()
    assert saved.json() == body
    return body


def track():
    response = httpx.get(f"{API}/aircraft/abc123/track", timeout=5)
    response.raise_for_status()
    return response.json()


def live():
    response = httpx.get(f"{API}/aircraft", params={"bbox": BBOX}, timeout=5)
    response.raise_for_status()
    return response.json()["aircraft"]


def test_int_02_duplicate_does_not_duplicate_history_or_rollback():
    select("duplicate")
    assert cycle("duplicate")["status"] == "succeeded"
    wait_for(lambda: live(), "live state")
    wait_for(lambda: track()["count"] > 0, "first committed observation")
    before = track()["count"]
    last_contact = live()[0]["last_contact"]
    batches = httpx.get(f"{API}/health", timeout=5).json()["batches_written_total"]
    assert cycle("duplicate")["status"] == "succeeded"
    wait_for(lambda: httpx.get(f"{API}/health", timeout=5).json()["batches_written_total"] > batches, "writer batch committed")
    assert track()["count"] == before
    assert live()[0]["last_contact"] == last_contact
    select("older")
    assert cycle("older")["status"] == "succeeded"
    assert live()[0]["last_contact"] == last_contact
    assert live()[0]["velocity"] == 250.0


@pytest.mark.parametrize("scenario", ["empty_null", "empty_list"])
def test_int_03_empty_cycles_and_eviction(scenario):
    select("old")
    assert cycle("old")["accepted"] == 1
    wait_for(lambda: live(), "old live aircraft", deadline_s=5)
    select(scenario)
    result = cycle(scenario)
    assert result["status"] == "succeeded" and result["accepted"] == 0 and result["rejected"] == 0
    wait_for(lambda: not live(), "aircraft eviction", deadline_s=10)


def test_int_04_malformed_row_does_not_discard_valid_row():
    select("mixed")
    result = cycle("mixed")
    assert result["status"] == "succeeded"
    assert (result["accepted"], result["rejected"]) == (1, 1)
    wait_for(lambda: live(), "valid aircraft")
    wait_for(lambda: track()["count"] == 1, "valid aircraft committed to history")


@pytest.mark.parametrize("scenario", ["error", "invalid_json"])
def test_int_05_upstream_failure_then_recovery(scenario):
    select(scenario)
    result = cycle(scenario)
    assert result["status"] == "failed" and result["accepted"] == 0
    assert live() == []
    assert track()["count"] == 0
    select("normal")
    result = cycle("normal")
    assert result["status"] == "succeeded" and result["accepted"] == 1
    wait_for(lambda: live(), "recovered live aircraft")


def test_int_06_unauthorized_refresh_retries_once():
    select("unauthorized_once")
    before = httpx.get(f"{FIXTURE}/requests", timeout=5).json()
    result = cycle("unauthorized_once")
    after = httpx.get(f"{FIXTURE}/requests", timeout=5).json()[len(before):]
    assert result["status"] == "succeeded", result
    assert sum(item["path"] == "/states/all" for item in after) == 2
    assert sum(item["path"] == "/token" for item in after) == 2
