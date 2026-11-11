"""Save synthetic AgentForge health and effects evidence before teardown."""
import json
import os
from pathlib import Path
from urllib.request import urlopen

path = Path(os.environ["TESTFORGE_EVIDENCE_DIR"])
path.mkdir(parents=True, exist_ok=True)
for name, url in {"health": os.environ["AGENTFORGE_API_URL"] + "/health", "stats": os.environ["AGENTFORGE_EFFECTS_URL"] + "/stats"}.items():
    try:
        with urlopen(url, timeout=5) as response:
            value = json.load(response)
    except (OSError, ValueError) as exc:
        value = {"capture_error": f"{type(exc).__name__}: {exc}"}
    (path / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
