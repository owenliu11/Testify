import time

import httpx
import pytest

from testforge.client import http_client, redact_headers
from testforge.wait import wait_for


def test_core_06_redaction_is_case_insensitive():
    assert redact_headers({"Authorization": "secret", "X-API-Key": "key", "Accept": "json"}) == {"Authorization": "[REDACTED]", "X-API-Key": "[REDACTED]", "Accept": "json"}


def test_core_07_client_surfaces_errors_and_closes():
    with http_client("http://example.test", 1) as client:
        client._transport = httpx.MockTransport(lambda request: httpx.Response(503, request=request))
        with pytest.raises(httpx.HTTPStatusError):
            client.get("/").raise_for_status()
    assert client.is_closed


def test_core_08_wait_returns_result():
    values = iter([None, {"ready": True}])
    assert wait_for(lambda: next(values), "ready", 1, 0.001) == {"ready": True}


def test_core_09_wait_timeout_includes_last_result():
    start = time.monotonic()
    with pytest.raises(TimeoutError, match="not ready"):
        wait_for(lambda: "" if False else None, "not ready", 0.02, 0.01)
    assert time.monotonic() - start < 1


def test_core_10_wait_does_not_retry_assertions():
    def fail():
        raise AssertionError("bad data")
    with pytest.raises(AssertionError, match="bad data"):
        wait_for(fail, "data", 1)
