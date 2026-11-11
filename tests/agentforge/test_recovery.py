"""Kill a real worker between publishing an effect and recording its result."""

import json
import os
from pathlib import Path
import re
import subprocess

import httpx
from testforge.wait import wait_for

from test_happy_path import API, EFFECTS


def test_worker_kill_recovers_without_duplicate_report():
    project = os.environ["TESTFORGE_AGENT_PROJECT"]
    assert re.fullmatch(r"tf_agent_[0-9]+", project)
    compose = ["docker", "compose", "-p", project, "-f", "targets/agentforge/compose.yaml"]
    evidence = Path(os.environ["TESTFORGE_EVIDENCE_DIR"])
    evidence.mkdir(parents=True, exist_ok=True)
    containers = []

    def docker(*args):
        result = subprocess.run(["docker", *args], check=True, text=True, capture_output=True, timeout=30)
        return (result.stdout + result.stderr if args[0] == "logs" else result.stdout).strip()

    def start_worker(run_id, worker_id, stall=False):
        command = compose + ["run", "-d", "--no-deps"]
        if stall:
            command += ["-e", "AF_STALL_AT=after_effect"]
        # The target's SIGSTOP fault hook must run in a child process: Linux
        # treats PID 1 specially and can ignore a stop signal sent to itself.
        command += ["worker", "sh", "-c", 'python -m app.worker --worker-id "$1" --run-id "$2"; exit $?', "testforge", worker_id, run_id]
        result = subprocess.run(command, check=True, text=True, capture_output=True, timeout=60)
        container = result.stdout.strip().splitlines()[-1]
        assert re.fullmatch(r"[a-f0-9]{12,64}", container), container
        containers.append(container)
        return container

    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            before = client.get(f"{EFFECTS}/stats").json()
            response = client.post(f"{API}/runs", json={"objective": "TestForge recovery", "repo_path": "sample_repo"})
            assert response.status_code == 202, response.text
            run_id = response.json()["id"]
            killed = start_worker(run_id, "testforge-killed", stall=True)

            def stalled():
                logs = docker("logs", killed)
                state = json.loads(docker("inspect", "--format", "{{json .State}}", killed))
                if not state["Running"]:
                    raise AssertionError(f"Worker exited before stall: {state}; {logs}")
                return logs if "stall point" in logs else None

            logs = wait_for(stalled, "worker to stall after report publication", deadline_s=90)
            (evidence / "worker-before-kill.log").write_text(logs + "\n")
            before_kill = client.get(f"{EFFECTS}/stats").json()
            assert before_kill["reports_applied"] == before["reports_applied"] + 1
            assert before_kill["report_deliveries"] == before["report_deliveries"] + 1
            docker("kill", "--signal", "KILL", killed)
            docker("wait", killed)
            state = json.loads(docker("inspect", "--format", "{{json .State}}", killed))
            assert state["ExitCode"] == 137 and not state["OOMKilled"], state
            replacement = start_worker(run_id, "testforge-replacement")

            def terminal():
                response = client.get(f"{API}/runs/{run_id}")
                response.raise_for_status()
                run = response.json()
                return run if run["status"] in {"COMPLETED", "FAILED"} else None

            run = wait_for(terminal, f"replacement to finish run {run_id}", deadline_s=90)
            stats = client.get(f"{EFFECTS}/stats").json()
            events = client.get(f"{API}/runs/{run_id}/events").json()
            (evidence / "recovery.json").write_text(json.dumps({"run": run, "events": events, "before": before, "before_kill": before_kill, "after": stats, "killed_state": state}, indent=2) + "\n")
            (evidence / "replacement.log").write_text(docker("logs", replacement) + "\n")
            assert run["status"] == "COMPLETED", run
            assert run["lease_generation"] >= 2, run
            assert stats["reports_applied"] == before["reports_applied"] + 1
            assert stats["report_deliveries"] == before["report_deliveries"] + 2
            assert stats["duplicates_suppressed"] == before["duplicates_suppressed"] + 1
            assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
            assert events[-1]["type"] == "run_completed"
            [url] = run["result"]["reports"]
            assert url.startswith(f"{EFFECTS}/reports/")
            report = client.get(url)
            report.raise_for_status()
            assert "test_subtract_fails" in report.json()["body"]
    finally:
        for container in containers:
            logs = subprocess.run(["docker", "logs", container], text=True, capture_output=True, timeout=30, check=False)
            (evidence / f"{container[:12]}.log").write_text(logs.stdout + logs.stderr)
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30, check=False)
