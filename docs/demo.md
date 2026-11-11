# TestForge demo

This is a presentation guide for the implementation in this repository. Commands take variable time when images must be built; prepare the environment and run them once before presenting. A full Phase 1 run is longer than the five-minute walkthrough.

## Prepare

Follow the README's fresh setup, start Docker, and set `SKYWATCH_DIR` and `AGENTFORGE_DIR` to the two pinned, clean checkouts. Install Chromium and pull `python:3.12-alpine`. In a terminal with no other TestForge stacks using the default ports, run the commands below once and keep the resulting reports available. Open the README architecture diagram and a successful [CI run](https://github.com/owenliu11/Testify/actions) with its artifact bundles. Review any logs before sharing them.

## Walkthrough

1. **The problem and boundary (0:00–1:00).** Show the README diagram and `src/testforge/`. Explain that pytest drives real applications, while each target owns its fixtures and Compose stack. Synthetic providers make inputs repeatable.
2. **SkyWatch integration (1:00–2:00).** Run `bash scripts/run-skywatch-isolated.sh tests/skywatch/integration/test_ingestion.py`. Show its JUnit and log under the printed report directory. The test checks a synthetic aircraft in both live state and historical storage, not just service health.
3. **Diagnose a deliberate regression (2:00–3:15).** Run `bash scripts/demo-regression.sh`. Open the printed evidence directory's `summary.txt`, `broken/`, and `restored/`. Explain that a disposable clone has leave events suppressed: the verifier confirms the application and input cycles worked before accepting the intended failure, then checks the restored code passes. The original SkyWatch checkout is unchanged.
4. **Second target (3:15–4:15).** Run `bash scripts/run-agentforge-isolated.sh tests/agentforge/test_recovery.py`. Open `recovery.json` and worker logs under its evidence directory. Explain the real worker container kill after report publication, a replacement worker, two deliveries, and one applied report.
5. **CI and limitations (4:15–5:00).** Show a successful workflow and its artifacts. Explain that separate jobs run each suite, another runs both target stacks together, and repeated passes increase confidence without proving no flakiness. Synthetic inputs trade live realism for reproducibility; the project is validated against two pinned targets.

If an image build or the network is slow, walk through saved evidence from the warm-up run or a CI artifact instead. Do not present sample output as a new live run.
