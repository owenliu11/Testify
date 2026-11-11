"""Load and validate a TestForge configuration file before anything starts.

The contract is documented in docs/configuration.md. Every problem is reported as
a ConfigError naming the setting, and relative paths resolve from the directory
that holds the configuration file, never from the current working directory.
"""

import math
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

SUPPORTED_VERSION = 1
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
ENV_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
RESERVED_ENV_PREFIX = "TESTFORGE_"
DEFAULT_COMPOSE_WAIT_TIMEOUT_SECONDS = 90.0
DEFAULT_READINESS_TIMEOUT_SECONDS = 45.0
DEFAULT_REPORTS_DIRECTORY = "reports"

TOP_LEVEL_KEYS = {"version", "name", "compose_file", "test_paths", "env", "readiness", "reports"}
READINESS_KEYS = {"compose_wait_timeout_seconds", "url", "timeout_seconds"}
REPORTS_KEYS = {"directory"}


class ConfigError(ValueError):
    """The configuration file is missing, unreadable, or invalid."""


@dataclass(frozen=True)
class Readiness:
    compose_wait_timeout_seconds: float
    url: str | None
    timeout_seconds: float


@dataclass(frozen=True)
class Config:
    name: str
    config_dir: Path
    compose_file: Path
    test_paths: tuple[Path, ...]
    env: Mapping[str, str]
    readiness: Readiness
    reports_directory: Path
    version: int = SUPPORTED_VERSION


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        with path.open("rb") as file:
            raw = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Could not parse {path}: {exc}") from exc
    config_dir = path.resolve().parent

    if "targets" in raw and "version" not in raw:
        raise ConfigError("This file uses the retired [targets.<name>] format; see docs/configuration.md for the version 1 contract")
    version = raw.get("version")
    if version is None:
        raise ConfigError("Missing required setting: version")
    if isinstance(version, bool) or not isinstance(version, int) or version != SUPPORTED_VERSION:
        raise ConfigError(f"Unsupported configuration version {version!r}; this TestForge supports version {SUPPORTED_VERSION}")
    if "profiles" in raw:
        raise ConfigError("profiles are not supported in configuration version 1")
    _reject_unknown(raw, TOP_LEVEL_KEYS, "top level")

    name = _string(_required(raw, "name"), "name")
    if not NAME_PATTERN.match(name):
        raise ConfigError("name must be 1-40 characters of lowercase letters, digits, '-' or '_', and start with a letter or digit")

    compose_file = _resolve(_string(_required(raw, "compose_file"), "compose_file"), config_dir)
    if not compose_file.is_file():
        raise ConfigError(f"compose_file does not exist or is not a file: {compose_file}")

    test_paths = _test_paths(_required(raw, "test_paths"), config_dir)
    env = _env(raw.get("env", {}))
    readiness = _readiness(raw.get("readiness", {}))
    reports_directory = _reports_directory(raw.get("reports", {}), config_dir)
    return Config(name, config_dir, compose_file, test_paths, env, readiness, reports_directory, version)


def _required(table: Mapping[str, object], key: str) -> object:
    if key not in table:
        raise ConfigError(f"Missing required setting: {key}")
    return table[key]


def _reject_unknown(table: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"Unknown setting at {where}: {', '.join(unknown)}")


def _table(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{field} must be a table")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a nonempty string")
    return value


def _positive_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{field} must be a positive finite number")
    return float(value)


def _resolve(value: str, config_dir: Path) -> Path:
    candidate = Path(value).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (config_dir / candidate).resolve()


def _test_paths(value: object, config_dir: Path) -> tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError("test_paths must be a nonempty list of paths")
    resolved = []
    for index, item in enumerate(value):
        path = _resolve(_string(item, f"test_paths[{index}]"), config_dir)
        if not path.exists():
            raise ConfigError(f"test_paths[{index}] does not exist: {path}")
        resolved.append(path)
    return tuple(resolved)


def _env(value: object) -> Mapping[str, str]:
    table = _table(value, "env")
    env: dict[str, str] = {}
    for key, item in table.items():
        if not ENV_KEY_PATTERN.match(key):
            raise ConfigError(f"env key {key!r} must be uppercase letters, digits and underscores, starting with a letter")
        if key.startswith(RESERVED_ENV_PREFIX):
            raise ConfigError(f"env key {key!r} is reserved; TestForge sets every {RESERVED_ENV_PREFIX}* variable itself")
        if not isinstance(item, str):
            raise ConfigError(f"env.{key} must be a string (quote numbers and booleans)")
        env[key] = item
    return MappingProxyType(env)


def _url(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{field} must be a URL")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ConfigError(f"Invalid {field}: {exc}") from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ConfigError(f"Invalid {field}: must be an http or https URL with a host")
    if parts.username or parts.password:
        raise ConfigError(f"Invalid {field}: credentials are not allowed in URLs")
    if parts.query or parts.fragment:
        raise ConfigError(f"Invalid {field}: query strings and fragments are not allowed")
    if port is not None and not 0 < port < 65536:
        raise ConfigError(f"Invalid {field}: port out of range")
    return value.rstrip("/")


def _readiness(value: object) -> Readiness:
    table = _table(value, "readiness")
    _reject_unknown(table, READINESS_KEYS, "readiness")
    compose_wait = _positive_number(table.get("compose_wait_timeout_seconds", DEFAULT_COMPOSE_WAIT_TIMEOUT_SECONDS), "readiness.compose_wait_timeout_seconds")
    url = _url(table["url"], "readiness.url") if "url" in table else None
    if "timeout_seconds" in table and url is None:
        raise ConfigError("readiness.timeout_seconds requires readiness.url")
    timeout = _positive_number(table.get("timeout_seconds", DEFAULT_READINESS_TIMEOUT_SECONDS), "readiness.timeout_seconds")
    return Readiness(compose_wait, url, timeout)


def _reports_directory(value: object, config_dir: Path) -> Path:
    table = _table(value, "reports")
    _reject_unknown(table, REPORTS_KEYS, "reports")
    return _resolve(_string(table.get("directory", DEFAULT_REPORTS_DIRECTORY), "reports.directory"), config_dir)
