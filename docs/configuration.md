# Configuration contract (version 1)

A TestForge project is described by one TOML file, conventionally `testforge.toml`, kept in the application's own repository next to its Compose file and tests. TestForge reads it, validates everything, and only then touches Docker. This page is the contract: the file format, what is validated, and the environment TestForge guarantees to the application's tests.

The contract does not mention any particular application. SkyWatch and AgentForge will be expressed through it in a later milestone.

## Example

```toml
version = 1
name = "sample-api"
compose_file = "compose.yaml"
test_paths = ["tests"]

[env]
# Passed to Compose and to pytest. Values must be synthetic; never real credentials.
SAMPLE_PORT = "18090"

[readiness]
# Primary signal: `docker compose up --wait` and the services' own healthchecks.
compose_wait_timeout_seconds = 90
# Optional extra check, polled after Compose reports the stack healthy.
url = "http://127.0.0.1:18090/health"
timeout_seconds = 45

[reports]
directory = "reports"
```

## Settings

Relative paths resolve from the directory that holds the configuration file, never from the current working directory. `~` is expanded. Absolute paths are kept as given.

| Setting | Required | Type | Rules |
|---|---|---|---|
| `version` | yes | integer | Must be `1`. Any other value, a string, a boolean, or a float is rejected. |
| `name` | yes | string | 1 to 40 characters of lowercase letters, digits, `-` or `_`, starting with a letter or digit. It becomes part of the Compose project name and of report paths. |
| `compose_file` | yes | path | Must exist and be a file. |
| `test_paths` | yes | list of paths | Nonempty. Every entry must exist (file or directory). Passed to pytest in order. |
| `[env]` | no | table of strings | See "Environment passthrough". Default: empty. |
| `readiness.compose_wait_timeout_seconds` | no | positive number | How long `docker compose up --wait` may take. Default `90`. |
| `readiness.url` | no | http or https URL | Polled after Compose reports healthy. Must have a host; no credentials, query string, or fragment; port 1 to 65535 if given. A trailing `/` is dropped. Default: none. |
| `readiness.timeout_seconds` | no | positive number | Deadline for polling `readiness.url`. Only allowed when `url` is set. Default `45`. |
| `reports.directory` | no | path | Where TestForge creates one unique directory per run. Need not exist yet. Default `reports`, relative to the configuration file. |

Unknown settings at any level are rejected by name, so a typo cannot be silently ignored. A `[profiles]` table is rejected with a message saying profiles are not part of version 1 (see "Decisions fixed for version 1").

A file in the retired `[targets.<name>]` layout is rejected with a message pointing here.

Numbers must be finite and greater than zero. Booleans are not numbers, and `"5"` is not a number.

## Environment passthrough

Keys under `[env]` are exported unchanged to both Compose (so the Compose file can interpolate them, for example to pick a loopback port) and to pytest. Rules:

- Keys match `^[A-Z][A-Z0-9_]*$`.
- Keys may not start with `TESTFORGE_`; that prefix belongs to TestForge.
- Values must be strings. Quote numbers and booleans in the TOML file.
- Values are logged and written into evidence without redaction. Put only synthetic values here. Real credentials belong in a mechanism outside the configuration file, which is out of scope for version 1.

## Readiness

Compose is the primary readiness signal. TestForge runs `docker compose up --wait` with `compose_wait_timeout_seconds` as the wait timeout, so every service the tests depend on should declare a healthcheck in the Compose file. Readiness means "Compose reported every service healthy or completed".

`readiness.url` is an optional second check for the common case where a healthy container is not yet a serving application. TestForge polls it with bounded polling (`testforge.wait.wait_for`) until it returns an HTTP 2xx or `timeout_seconds` expires. On timeout the error includes the last observed status code or connection error, so a stuck start is distinguishable from a wrong port.

Other readiness kinds (TCP, command, log line) are not part of version 1.

## Reports

Each run creates a unique directory inside `reports.directory` and writes its JUnit result, Compose logs, a copy of the resolved configuration (without secrets, because the configuration must not contain any), and whatever the tests write into their evidence directory. Later runs never overwrite earlier ones.

## The environment TestForge guarantees to tests

The configuration file is only half the contract. The other half is what the application's tests may rely on at runtime. For every run TestForge exports exactly these variables to Compose and to pytest, plus every key under `[env]`:

| Variable | Value |
|---|---|
| `TESTFORGE_BASE_URL` | Scheme, host and port of `readiness.url` (for example `http://127.0.0.1:18090`), or an empty string when no readiness URL is configured. |
| `TESTFORGE_COMPOSE_PROJECT` | The run's unique Compose project name. Lowercase letters, digits, `-` and `_`. |
| `TESTFORGE_COMPOSE_FILE` | Absolute path of the Compose file in use. |
| `TESTFORGE_EVIDENCE_DIR` | Absolute path of a directory the tests may write artifacts into. It is collected with the run's evidence. |

Tests that need to stop, restart, or inspect a service should do so with an argument list built from the two Compose variables, for example:

```python
import os, subprocess
compose = ["docker", "compose", "-p", os.environ["TESTFORGE_COMPOSE_PROJECT"], "-f", os.environ["TESTFORGE_COMPOSE_FILE"]]
subprocess.run([*compose, "stop", "api"], check=True, timeout=30)
```

No other `TESTFORGE_*` variable is promised. The Python side of this contract is `testforge.environment.runtime_environment`, and `testforge.environment.EXPORTED_KEYS` lists the four names.

## Decisions fixed for version 1

- **One stack per run.** TestForge starts the Compose stack once, runs every test path against it, and tears the stack down. Running a fresh stack per test, varying the environment per test, enabling Compose profiles for some tests, or starting a subset of services are not supported in version 1. A `[profiles.<name>]` table is reserved for that purpose in a later version and is rejected today so that nobody depends on it by accident.
- **Compose first, HTTP second.** Readiness relies on Compose healthchecks; the HTTP URL is an optional extra.
- **No secrets in the file.** Everything in the configuration may be printed and saved.

## Validation errors

Every problem raises `testforge.config.ConfigError` (a `ValueError`) with a message that names the setting, for example:

```text
Missing required setting: compose_file
Unsupported configuration version 2; this TestForge supports version 1
name must be 1-40 characters of lowercase letters, digits, '-' or '_', and start with a letter or digit
compose_file does not exist or is not a file: /app/nope.yaml
test_paths[1] does not exist: /app/missing
Unknown setting at readiness: retries
env key 'TESTFORGE_BASE_URL' is reserved; TestForge sets every TESTFORGE_* variable itself
Invalid readiness.url: credentials are not allowed in URLs
readiness.timeout_seconds requires readiness.url
profiles are not supported in configuration version 1
```

The loader stops at the first problem. Nothing is started before the configuration is fully valid.

## Python API

```python
from pathlib import Path
from testforge.config import load_config, ConfigError
from testforge.environment import runtime_environment

config = load_config(Path("testforge.toml"))
env = runtime_environment(config, compose_project="tf_sample-api_20261111t120000z_1234", evidence_dir=Path("reports/run/evidence"))
```

`Config` is a frozen dataclass with `name`, `config_dir`, `compose_file`, `test_paths`, `env` (read-only mapping), `readiness` (`compose_wait_timeout_seconds`, `url`, `timeout_seconds`), `reports_directory`, and `version`.
