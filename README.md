# TestForge

TestForge exercises real application integrations with local, synthetic dependencies. The current starter scenario verifies that SkyWatch ingests one synthetic aircraft into live state and history.

## Run the SkyWatch starter scenario

Requirements: Python 3.12, Docker Compose, and a SkyWatch checkout at commit `e83e675a66fa7cf8e00a1b28397be1f08a662832` (release `v0.4.1`). Set `SKYWATCH_DIR` to its absolute path.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install .
docker compose -p tf_skywatch -f targets/skywatch/compose.yaml up --build -d --wait
.venv/bin/python -m pytest tests/core tests/skywatch/api tests/skywatch/integration/test_ingestion.py -v --junitxml=reports/skywatch/junit.xml
docker compose -p tf_skywatch -f targets/skywatch/compose.yaml down -v
```

The last command removes this Compose project's test database and volumes. Ports 18000 and 18080 must be available. The fixture uses invented data and dummy credentials. Reports are local and ignored by Git.

The CI workflow pins the same release commit and saves the JUnit report. If SkyWatch is private, configure a `SKYWATCH_READ_TOKEN` repository secret with read access to it.

See [baseline](docs/baseline.md) for current milestone status and limitations.

## M2 isolated scenarios

The timestamp regressions require SkyWatch `v0.4.1`. Point `SKYWATCH_DIR` to a checkout of that release and run:

```sh
export SKYWATCH_DIR="$HOME/skywatch"
bash scripts/run-skywatch-isolated.sh
```

The script starts a fresh, dedicated Compose project per scenario, saves JUnit results and logs under `reports/skywatch/isolated/`, and removes each test database afterward. See [M2 risk traceability](docs/m2-risk-traceability.md) for known coverage.

## M3 real-time and browser tests

Install the browser once with `.venv/bin/python -m playwright install chromium`. The isolated runner also runs the WebSocket scenarios and three browser journeys against a built Vite preview frontend. Each scenario uses fresh application state. Browser screenshots and traces are retained on failure under the run's `reports/skywatch/isolated/` directory. Map tiles are replaced by a local blank fixture; the application, API, and WebSocket remain real.

To run only M3 checks:

```sh
bash scripts/run-skywatch-isolated.sh tests/skywatch/ws tests/skywatch/ui
```

The UI uses loopback port 15173. Set `TF_SKYWATCH_UI_PORT`, `TF_SKYWATCH_API_PORT`, and `TF_SKYWATCH_FIXTURE_PORT` to distinct free ports for concurrent runs. When using an installed Chrome on macOS instead of Playwright's Chromium, set `TESTFORGE_BROWSER_CHANNEL=chrome`. See [M3 traceability](docs/m3-realtime-traceability.md) for scenario details.

## M4 Phase 1 and regression demo

With `SKYWATCH_DIR` pointing to the pinned SkyWatch checkout and Chromium installed, run `bash scripts/run-phase-one.sh`. This runs the core, API, isolated SkyWatch scenarios, and the controlled regression demo; it exits nonzero for failures, unexpected skips, or an empty suite. Reports are written under `reports/skywatch/phase-one/`.

Run only the controlled demonstration with `bash scripts/demo-regression.sh`. It changes a disposable local clone, confirms WS-02 fails specifically because the leave event is missing, and then restores the source and requires a pass. See [the regression guide](docs/m4-regression-demo.md) for the evidence and remaining reproducibility limits.

## AgentForge spike

Use an AgentForge checkout at `84b1c95aaa98c5855ab627aff141cdf12cac8da4`, Docker Compose, and the Python environment above. The worker accesses the Docker socket to run the fixture's tests in a disposable container. Ports 18010 and 18011 must be available. Set `AGENTFORGE_DIR` to the absolute checkout path, with no trailing slash:

```sh
export AGENTFORGE_DIR="$HOME/agentforge"
docker pull python:3.12-alpine
docker compose -p tf_agentforge_spike -f targets/agentforge/compose.yaml up --build -d --wait --wait-timeout 120
.venv/bin/python -m pytest tests/agentforge -v --junitxml=reports/agentforge/junit.xml
docker compose -p tf_agentforge_spike -f targets/agentforge/compose.yaml logs --no-color > reports/agentforge/compose.log
docker compose -p tf_agentforge_spike -f targets/agentforge/compose.yaml down -v
```

The last command deletes only this Compose project's test database. The scenario confirms the agent publishes a report containing the fixture's deliberately failing test; completion does not mean the fixture tests all pass. This spike has been verified locally, but is not yet part of CI.
