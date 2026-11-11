"""Black-box spike for the pinned AgentForge target."""

import os

import httpx
from testforge.wait import wait_for

API = os.environ.get("AGENTFORGE_API_URL", "http://127.0.0.1:18010").rstrip("/")
EFFECTS = os.environ.get("AGENTFORGE_EFFECTS_URL", "http://127.0.0.1:18011").rstrip("/")


def test_run_publishes_fixture_report() -> None:
    with httpx.Client(timeout=5, trust_env=False) as client:
        health = client.get(f"{API}/health")
        health.raise_for_status()
        assert health.json() == {"status": "ok", "db": "up"}
        before = client.get(f"{EFFECTS}/stats")
        before.raise_for_status()
        before_count = before.json()["reports_applied"]

        response = client.post(
            f"{API}/runs", json={"objective": "TestForge spike", "repo_path": "sample_repo"}
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]
        def terminal_run():
            response = client.get(f"{API}/runs/{run_id}")
            response.raise_for_status()
            run = response.json()
            return run if run["status"] in {"COMPLETED", "FAILED"} else None

        run = wait_for(terminal_run, f"run {run_id} to finish", deadline_s=90, interval_s=0.2)

        assert run["status"] == "COMPLETED", run
        events_response = client.get(f"{API}/runs/{run_id}/events")
        events_response.raise_for_status()
        events = events_response.json()
        assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
        assert events[0]["type"] == "run_created"
        assert events[-1]["type"] == "run_completed"
        [report_url] = run["result"]["reports"]
        assert report_url.startswith(f"{EFFECTS}/reports/")
        report = client.get(report_url)
        report.raise_for_status()
        assert "test_subtract_fails" in report.json()["body"]
        stats = client.get(f"{EFFECTS}/stats")
        stats.raise_for_status()
        assert stats.json()["reports_applied"] == before_count + 1
