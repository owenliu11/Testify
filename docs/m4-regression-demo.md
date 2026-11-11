# M4: controlled missing-leave regression

The `scripts/demo-regression.sh` command clones the pinned SkyWatch release into a temporary directory, creates a local disposable `demo/drop-leave-events` branch, and intentionally suppresses WebSocket leave events. It never changes the original SkyWatch checkout. It runs only `WS-02` on an isolated stack and requires the missing-leave assertion to fail.

The verifier requires all of the following before treating that failure as valid: the API health is `ok`; all three synthetic provider cycles succeeded; three provider requests occurred; entry and update frames arrived; the aircraft's API record moved outside the viewport; and no leave event arrived before the deadline. The script then restores the source in the disposable clone, confirms it matches the pinned commit, and requires the same test to pass. Any other failure makes the demonstration fail.

Each run writes separate broken and restored JUnit files, cycle and frame records, aircraft detail, fixture requests, health snapshots, container logs, and a summary under `reports/skywatch/regression-demo/`. The CI workflow runs the demonstration and uploads its evidence alongside the acceptance reports. Results are synthetic; no live provider data is used.

The Phase 1 scope is the independently tested core and SkyWatch API, integration, outages, WebSocket, and browser suites. AgentForge's complete cross-target acceptance remains the M5 portability milestone. Direct Python dependencies are pinned; Docker tags and transitive dependencies can still change, so identical source commits alone do not guarantee identical runtime environments.
