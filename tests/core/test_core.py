import time
from pathlib import Path

import httpx
import pytest
from jsonschema import ValidationError, validate

from testforge.client import http_client, redact_headers
from testforge.config import load_target
from testforge.wait import wait_for


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "targets.toml"
    path.write_text('[targets.demo]\nrevision="abc"\napi_base_url="http://localhost:1234"\nrequest_timeout=2\nreadiness_deadline=3\n')
    return path


def test_core_01_load_valid_config(config):
    assert load_target(config, "demo").api_base_url == "http://localhost:1234"


def test_core_02_reject_unknown_target(config):
    with pytest.raises(ValueError, match="Unknown target"):
        load_target(config, "other")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://user:secret@localhost", "http://localhost:bad", "http://localhost?token=secret"])
def test_core_03_reject_bad_or_secret_urls(config, url):
    config.write_text(config.read_text().replace("http://localhost:1234", url))
    with pytest.raises(ValueError, match="Invalid api_base_url"):
        load_target(config, "demo")


def test_core_04_reject_missing_setting(config):
    config.write_text(config.read_text().replace('revision="abc"\n', ""))
    with pytest.raises(ValueError, match="revision"):
        load_target(config, "demo")


@pytest.mark.parametrize("value", ["0", "-1", "nan", "true"])
def test_core_05_reject_bad_timeouts(config, value):
    config.write_text(config.read_text().replace("request_timeout=2", f"request_timeout={value}"))
    with pytest.raises(ValueError, match="request_timeout"):
        load_target(config, "demo")


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


def test_core_11_schema_rejects_malformed_response():
    import json
    schema = json.loads((Path(__file__).parents[2] / "targets/skywatch/contracts/aircraft.schema.json").read_text())
    with pytest.raises(ValidationError):
        validate({"as_of": "now", "count": "one", "truncated": False, "aircraft": []}, schema)
