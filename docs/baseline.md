# Baseline and milestone status

- SkyWatch target: release `v0.4.1`, commit `e83e675a66fa7cf8e00a1b28397be1f08a662832`. The original M1 target was `413a8237fdcf9afeaa9e495f9e6e96c720bcf18f`.
- AgentForge target: `84b1c95aaa98c5855ab627aff141cdf12cac8da4`, selected instead of the guide's older `0e41dcc` because it adds a dedicated TestForge target contract and isolated stack.
- SkyWatch requires Docker, a TimescaleDB container, Redis, a synthetic provider, and the API. The test uses ports 18000 and 18080 and no real provider credentials.
- The SkyWatch starter scenario passed locally and in GitHub Actions, with evidence saved in run 42892721167. The AgentForge happy-path spike passed locally; it is not yet included in CI.
- Licensing for TestForge and redistribution of the target repositories has not yet been decided. No license is implied by this document.
- M2 has passed its local core, API, isolated integration, timestamp regression, and dependency-outage checks. The SkyWatch fix is merged and tagged, and TestForge pins its release commit; see [risk traceability](m2-risk-traceability.md).

## Spike: shared needs

Both targets need configurable HTTP endpoints, readiness checks, deadline-based polling with useful last-state diagnostics, isolated Compose projects, and saved test results and logs. AgentForge additionally needs run-specific event and report checks, a worker, and access to Docker for its short-lived test sandbox. SkyWatch needs a synthetic provider and ingestion-specific checks. Keep those target-specific behaviors out of the shared core. The AgentForge fixture deliberately contains a failing test: the agent run is successful when it reports that failure accurately.
