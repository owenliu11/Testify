"""Dependency outages run only inside the dedicated TestForge project."""

import os
import re
import subprocess

import httpx
import pytest

from testforge.wait import wait_for

API = os.getenv("API_BASE_URL", "http://127.0.0.1:18000")


@pytest.mark.parametrize(("service", "field"), [("db", "database"), ("redis", "redis")])
def test_isolated_dependency_outage_and_recovery(service, field):
    project = os.environ.get("TESTFORGE_COMPOSE_PROJECT", "")
    if not re.fullmatch(r"tf_m2_[0-9]+", project):
        pytest.fail("Run outage tests with scripts/run-skywatch-isolated.sh")
    compose = ["docker", "compose", "-p", project, "-f", "targets/skywatch/compose.yaml"]

    def health():
        response = httpx.get(f"{API}/health", timeout=5, trust_env=False)
        response.raise_for_status()
        return response.json()

    assert health()["status"] == "ok"
    try:
        subprocess.run([*compose, "stop", service], check=True, timeout=30)
        degraded = wait_for(
            lambda: (value if (value := health())["status"] == "degraded" and value[field] is False else None),
            f"health to report {service} outage", deadline_s=30, retry_on=(httpx.HTTPError,),
        )
        assert degraded["status"] == "degraded"
    finally:
        subprocess.run([*compose, "start", service], check=True, timeout=30)
    wait_for(lambda: health()["status"] == "ok", f"health to recover after {service} restart", deadline_s=45, retry_on=(httpx.HTTPError,))
