"""The environment TestForge guarantees to Compose and to pytest for one run.

This is the test-side half of the contract in docs/configuration.md. Tests read
these variables instead of guessing ports, project names, or output locations.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

from testforge.config import Config

COMPOSE_PROJECT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

BASE_URL = "TESTFORGE_BASE_URL"
COMPOSE_PROJECT = "TESTFORGE_COMPOSE_PROJECT"
COMPOSE_FILE = "TESTFORGE_COMPOSE_FILE"
EVIDENCE_DIR = "TESTFORGE_EVIDENCE_DIR"
EXPORTED_KEYS = (BASE_URL, COMPOSE_PROJECT, COMPOSE_FILE, EVIDENCE_DIR)


def base_url(readiness_url: str | None) -> str:
    """The scheme, host and port of the readiness URL, or '' when none is configured."""
    if readiness_url is None:
        return ""
    parts = urlsplit(readiness_url)
    return f"{parts.scheme}://{parts.netloc}"


def runtime_environment(config: Config, *, compose_project: str, evidence_dir: Path) -> dict[str, str]:
    """Variables exported to Compose and pytest: the TESTFORGE_* set plus the config's [env] table."""
    if not COMPOSE_PROJECT_PATTERN.match(compose_project):
        raise ValueError(f"Invalid Compose project name: {compose_project!r}")
    exported = {
        BASE_URL: base_url(config.readiness.url),
        COMPOSE_PROJECT: compose_project,
        COMPOSE_FILE: str(config.compose_file),
        EVIDENCE_DIR: str(Path(evidence_dir).resolve()),
    }
    exported.update(config.env)
    return exported
