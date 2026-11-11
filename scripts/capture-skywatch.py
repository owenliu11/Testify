"""Collect bounded, synthetic-only diagnostics before an isolated stack is removed."""

import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

directory = Path(os.environ["TESTFORGE_EVIDENCE_DIR"])
directory.mkdir(parents=True, exist_ok=True)
for name, url in {
    "health.json": os.environ["API_BASE_URL"] + "/health",
    "fixture_requests.json": os.environ["FIXTURE_URL"] + "/requests",
}.items():
    try:
        with urlopen(url, timeout=5) as response:
            value = json.load(response)
    except (OSError, URLError, ValueError) as exc:
        value = {"capture_error": f"{type(exc).__name__}: {exc}"}
    (directory / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
