# TestForge

TestForge exercises real application integrations with local, synthetic dependencies. The current starter scenario verifies that SkyWatch ingests one synthetic aircraft into live state and history.

## Run the SkyWatch starter scenario

Requirements: Python 3.12, Docker Compose, and a SkyWatch checkout at commit `8182c2628a154f624df7b9c39366d5e80987626d` on branch `codex/m2-timestamp-fixes`. Set `SKYWATCH_DIR` to its absolute path.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install .
docker compose -p tf_skywatch -f targets/skywatch/compose.yaml up --build -d --wait
.venv/bin/python -m pytest tests/core tests/skywatch/api tests/skywatch/integration/test_ingestion.py -v --junitxml=reports/skywatch/junit.xml
docker compose -p tf_skywatch -f targets/skywatch/compose.yaml down -v
```

The last command removes this Compose project's test database and volumes. Ports 18000 and 18080 must be available. The fixture uses invented data and dummy credentials. Reports are local and ignored by Git.

The CI workflow pins the same candidate and saves the JUnit report. If SkyWatch is private, configure a `SKYWATCH_READ_TOKEN` repository secret with read access to it.

See [baseline](docs/baseline.md) for current milestone status and limitations.

## M2 isolated scenarios

The timestamp regressions require the proposed SkyWatch fix on branch `codex/m2-timestamp-fixes` (local commit `8182c2628a154f624df7b9c39366d5e80987626d`). Once that revision is available locally, point `SKYWATCH_DIR` to its checkout and run:

```sh
export SKYWATCH_DIR="$PWD/.worktrees/skywatch-m2"
bash scripts/run-skywatch-isolated.sh
```

The script starts a fresh, dedicated Compose project per scenario, saves JUnit results and logs under `reports/skywatch/isolated/`, and removes each test database afterward. See [M2 risk traceability](docs/m2-risk-traceability.md) for known coverage and remaining release work. The updated local workflow includes these scenarios; the workflow currently on GitHub still runs the original starter test.

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
