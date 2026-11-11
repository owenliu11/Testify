# Architecture, test strategy, and troubleshooting

## Boundaries

TestForge uses pytest as its runner; `src/testforge/` contains reusable configuration validation, HTTP-client, and bounded-polling helpers. Target-specific behavior remains in `tests/skywatch/`, `tests/agentforge/`, the Compose files under `targets/`, and the synthetic SkyWatch fixture under `fixtures/`. The shell runners arrange each scenario's stack and evidence; they do not require either target's production deployment.

SkyWatch runs its actual API against a synthetic provider, a dedicated TimescaleDB instance, and Redis. UI scenarios build the target frontend and use Playwright; their map tiles are locally substituted. AgentForge runs its actual API and worker against a dedicated PostgreSQL database and mock effects API. Its worker talks to the host Docker daemon to launch a disposable sandbox for its fixture repository. Each target uses its own Compose project and ports; the CI combined job starts both at once and runs one representative test for each.

## Coverage and evidence

- **Shared core:** configuration, HTTP helpers, and deadline-based polling.
- **SkyWatch:** API contracts, ingestion into live state and history, selected risk and timestamp regressions, dependency outages, WebSocket events, and three browser journeys. See [M2](m2-risk-traceability.md) and [M3](m3-realtime-traceability.md) for coverage and gaps.
- **AgentForge:** report creation, invalid requests, missing IDs, step-limit failure, and recovery after killing a worker after publication. The recovery check verifies a new lease, a completed run, one report applied, two deliveries, and one duplicate suppressed. See [M5](m5-portability.md).
- **Regression demo:** a disposable clone suppresses one WebSocket leave event. Evidence must show the provider and API worked and the expected event was missing; restoring the code must make the same test pass. See [M4](m4-regression-demo.md).

Isolated runners create fresh project state per scenario, capture JUnit XML and service logs, and remove only their own Compose project and associated test data. SkyWatch also captures health and provider activity; WebSocket scenarios record frames and browser failures retain screenshots and traces. AgentForge captures health and effects counters, with detailed recovery evidence. CI uploads reports even when a test step fails, subject to artifacts actually having been created. Test inputs and configured credentials are synthetic; review artifacts before sharing if changing those inputs.

The workflow tests both target suites independently and also runs a positive scenario for each while both stacks are running. Five successful unchanged-commit runs increase confidence but do not prove the absence of intermittent failures. Integration tests cannot prove live-provider behavior, performance at scale, or that every regression is covered. Image tags, package registries, and transitive dependencies are not fully locked. TestForge has been exercised against the two pinned applications, not arbitrary third-party services.

## Troubleshooting

- **Docker unavailable or port in use:** start Docker and select free ports using the environment variables in the README. Clean up only the project created for your test; `down -v` deletes that project's test volumes.
- **Wrong target version or dirty checkout:** check `git -C "$SKYWATCH_DIR" status --short` and `git -C "$SKYWATCH_DIR" rev-parse HEAD`, and do the same for AgentForge. Use the pins in the README. The AgentForge isolated runner rejects a dirty or different checkout.
- **Missing browser:** run `.venv/bin/python -m playwright install chromium`; on Linux install the required system dependencies with Playwright's `--with-deps` option.
- **Failure or timeout:** open the corresponding JUnit XML and service log under `reports/`, then inspect the captured health, fixture, frames, or recovery files for that scenario. For browser failures open its retained Playwright trace with `.venv/bin/python -m playwright show-trace PATH_TO_TRACE.zip`.
- **AgentForge sandbox cannot start:** check that Docker is running, the Docker socket is available to the worker, the checkout path is shared with Docker Desktop, and `python:3.12-alpine` is available. Never mount a Docker socket into an untrusted workload.
