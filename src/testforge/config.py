"""Validate target configuration before starting services."""

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Target:
    name: str
    revision: str
    api_base_url: str
    request_timeout: float
    readiness_deadline: float
    ui_base_url: str | None = None
    ws_url: str | None = None


def _url(value: object, schemes: set[str], field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a URL")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"Invalid {field}") from exc
    if parts.scheme not in schemes or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or (port is not None and not 0 < port < 65536):
        raise ValueError(f"Invalid {field}")
    return value.rstrip("/")


def load_target(path: Path, name: str) -> Target:
    with path.open("rb") as file:
        targets = tomllib.load(file).get("targets", {})
    if name not in targets:
        raise ValueError(f"Unknown target: {name}")
    config = targets[name]
    try:
        revision = config["revision"]
        api = _url(config["api_base_url"], {"http", "https"}, "api_base_url")
        timeout = config["request_timeout"]
        deadline = config["readiness_deadline"]
    except KeyError as exc:
        raise ValueError(f"Missing target setting: {exc.args[0]}") from exc
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError("revision must be nonempty")
    for field, value in (("request_timeout", timeout), ("readiness_deadline", deadline)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{field} must be a positive finite number")
    ui = _url(config["ui_base_url"], {"http", "https"}, "ui_base_url") if "ui_base_url" in config else None
    ws = _url(config["ws_url"], {"ws", "wss"}, "ws_url") if "ws_url" in config else None
    return Target(name, revision, api, timeout, deadline, ui, ws)
