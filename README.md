# TestForge

TestForge exercises real application integrations with local, synthetic dependencies. The current starter scenario verifies that SkyWatch ingests one synthetic aircraft into live state and history.

## Run the SkyWatch starter scenario

Requirements: Python 3.12, Docker Compose, and a SkyWatch checkout at commit `413a8237fdcf9afeaa9e495f9e6e96c720bcf18f`. By default the checkout is expected at `../skywatch`; set `SKYWATCH_DIR` to its absolute path otherwise.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install .
docker compose -p tf_skywatch -f targets/skywatch/compose.yaml up --build -d --wait
.venv/bin/python -m pytest tests/skywatch -v --junitxml=reports/skywatch/junit.xml
docker compose -p tf_skywatch -f targets/skywatch/compose.yaml down -v
```

The last command removes this Compose project's test database and volumes. Ports 18000 and 18080 must be available. The fixture uses invented data and dummy credentials. Reports are local and ignored by Git.

CI uses the same pinned SkyWatch revision and saves the JUnit report. If SkyWatch is private, configure a `SKYWATCH_READ_TOKEN` repository secret with read access to it.

See [baseline](docs/baseline.md) for current milestone status and limitations.
