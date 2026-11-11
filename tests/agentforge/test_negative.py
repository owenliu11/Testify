"""Negative contracts against a fresh AgentForge stack."""

import uuid

import httpx
import pytest
from testforge.wait import wait_for

from test_happy_path import API, EFFECTS


@pytest.mark.parametrize("payload", [
    {"repo_path": "../outside"},
    {"repo_path": "does-not-exist"},
    {"repo_path": "sample_repo", "max_steps": 0},
    {"repo_path": "sample_repo", "max_steps": 51},
])
def test_invalid_run_is_rejected(payload):
    with httpx.Client(timeout=5, trust_env=False) as client:
        before = client.get(f"{EFFECTS}/stats").json()
        response = client.post(f"{API}/runs", json=payload)
        assert response.status_code == 422, response.text
        assert client.get(f"{EFFECTS}/stats").json() == before


def test_unknown_run_is_not_found():
    with httpx.Client(timeout=5, trust_env=False) as client:
        run_id = uuid.uuid4()
        assert client.get(f"{API}/runs/{run_id}").status_code == 404
        assert client.get(f"{API}/runs/{run_id}/events").status_code == 404


def test_max_steps_fails_without_publishing():
    with httpx.Client(timeout=5, trust_env=False) as client:
        before = client.get(f"{EFFECTS}/stats").json()
        response = client.post(f"{API}/runs", json={"repo_path": "sample_repo", "max_steps": 1})
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]

        def terminal():
            response = client.get(f"{API}/runs/{run_id}")
            response.raise_for_status()
            run = response.json()
            return run if run["status"] in {"COMPLETED", "FAILED"} else None

        run = wait_for(terminal, f"run {run_id} to fail", deadline_s=90)
        assert run["status"] == "FAILED", run
        assert "MAX_STEPS_EXCEEDED" in run["error"]
        assert client.get(f"{EFFECTS}/stats").json() == before
