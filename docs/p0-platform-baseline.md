# P0: Platform baseline

Recorded on 2026-11-11 before any platform extraction work. This is the before-state that later milestones compare against.

## Base branch and revisions

| Repository | Revision | Note |
|---|---|---|
| TestForge (`owenliu11/Testify`) | `d2ece1f` | `main` after the M6 merge (PR #5). The platform branch `platform/p0-baseline` starts here. |
| SkyWatch (`owenliu11/skywatch`) | `e83e675a66fa7cf8e00a1b28397be1f08a662832` | Release `v0.4.1`. Clean checkouts exist at `~/skywatch`, `../skywatch`, and `.worktrees/m6-fresh.FM9xQk/skywatch`. |
| AgentForge (`owenliu11/AgentForge`) | `84b1c95aaa98c5855ab627aff141cdf12cac8da4` | Clean checkouts exist at `~/agentforge`, `../agentforge`, and `.worktrees/m6-fresh.FM9xQk/agentforge`. |

The merged `codex/m6-publish` branch was deleted locally. The personal `output/` directory is now listed in `.gitignore` and was not modified.

## Existing runners kept as reference

These stay in place, unchanged, until their replacements pass equivalent checks:

- `scripts/run-phase-one.sh`: core tests, SkyWatch API tests against one starter stack, then the isolated SkyWatch scenarios and the regression demonstration.
- `scripts/run-skywatch-isolated.sh`: one fresh Compose project per SkyWatch test node, with per-node environment and Compose-profile special cases.
- `scripts/run-agentforge-isolated.sh`: one fresh Compose project per AgentForge test node, with a service subset for the recovery scenario and a pinned-commit check.
- `scripts/demo-regression.sh` and `scripts/verify-regression.py`: the controlled missing-leave regression demonstration.
- `scripts/verify-junit.py`: the empty-suite and unexpected-skip gate.
- `scripts/capture-skywatch.py` and `scripts/capture-agentforge.py`: post-run evidence capture.

Where application coupling lives, and which milestone replaces each piece, is tabulated in the build guide (section 3).

## Local environment

- macOS, Docker Desktop 27.3.1, Docker Compose v2.30.3.
- Python 3.12 virtual environment at `.venv` with the pinned dependencies installed.
- `SKYWATCH_DIR` and `AGENTFORGE_DIR` are not set globally; each run sets them explicitly.

## Local test results

Evidence for this baseline is under `reports/p0/` (ignored by Git).

| Suite | Command | Result |
|---|---|---|
| Core | `.venv/bin/python -m pytest tests/core --junitxml=reports/p0/core.xml` | 17 passed, 0 skipped, 0 errors. `verify-junit.py` accepted it. |
| AgentForge isolated | `AGENTFORGE_DIR=~/agentforge TESTFORGE_REPORT_DIR=reports/p0/agentforge bash scripts/run-agentforge-isolated.sh` | Exit 0. 8 isolated scenarios, each 1 test: 8 passed, 0 skipped, 0 errors. Every scenario's JUnit passed `verify-junit.py`; each Compose project was removed. |
| SkyWatch phase one | `SKYWATCH_DIR=~/skywatch TESTFORGE_PHASE1_REPORT_DIR=reports/p0/skywatch-phase-one bash scripts/run-phase-one.sh` | Exit 0. Core 17 passed; API 12 passed against the starter stack; 20 isolated scenarios each 1 test, 20 passed, 0 skipped; regression demo produced the intended WS-02 missing-leave failure on the patched clone and passed on the restored source. No `tf_` Compose projects were left behind. |

## GitHub Actions startup problem

This is an infrastructure problem, recorded separately from test results. It is **not** a failing test.

Repository visibility is public, so Actions minute quotas and spending limits do not apply. The workflow file `.github/workflows/skywatch.yml` was not changed by PR #5. GitHub's status page reported Actions as operational at the time of recording.

Timeline on 2026-11-11 (UTC), all for workflow "SkyWatch integration":

| Run ID | Trigger | Branch / commit | Outcome |
|---|---|---|---|
| 43091425324 | pull_request | `codex/m5-portability` @ `de4a603` | success |
| 43091501839, 43091506603, 43091510521, 43091515220 | workflow_dispatch | `codex/m5-portability` @ `de4a603` | success (four of the five-run gate for M5) |
| 43093209949 | push | `main` @ `3455943` (M5 merge) | success, 20:05 |
| 43095178884 | push | `codex/m6-publish` @ `659fdc5` | **queued, never started** |
| 43095238783 | pull_request | `codex/m6-publish` @ `659fdc5` | **queued, never started** |
| 43095250878, 43095253990, 43095257291, 43095260368 | workflow_dispatch | `codex/m6-publish` @ `659fdc5` | **startup_failure, zero jobs created** |
| 43096365313 | workflow_dispatch | `codex/m6-publish` @ `659fdc5` | **startup_failure, zero jobs** |
| 43096873296 | workflow_dispatch | `main` @ `3455943` | **startup_failure, zero jobs**, 20:34. Same commit and workflow file that succeeded at 20:05. |
| 43097222466 | push | `main` @ `d2ece1f` (M6 merge) | **queued, never started** (over an hour at time of recording) |

Key observation: commit `3455943` with an identical workflow file succeeded at 20:05 and failed at startup at 20:34. The failure is therefore not caused by the repository contents.

Consequences:

- M6 was merged without any passing run on its candidate (`659fdc5`) or its merge commit (`d2ece1f`). The five-consecutive-clean-runs gate from the M6 checklist was never met and is carried forward to P7.
- Nothing in P6 can be validated until GitHub creates jobs for this repository again.

For a support ticket: the API request that fetched run 43096873296 returned `X-GitHub-Request-Id: D15C:7B849:12C0411:3B6844F:6AF4DDB2`. Capture the request ID shown on the run's own page in the browser as well, since that is the one tied to the failed startup.

Checked: the repository's Actions API reports `enabled: true`, `allowed_actions: all`, and the workflow state is `active`. Not yet checked: whether re-running a failed run after some time creates jobs. The runs were left as they are; no retries were made.
