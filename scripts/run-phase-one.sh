#!/usr/bin/env bash
# Run Phase 1 locally with isolated state and project-scoped cleanup.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PYTHON="${TESTFORGE_PYTHON:-.venv/bin/python}"
PROJECT="tf_phase1_$$"
COMPOSE=(docker compose -p "$PROJECT" -f targets/skywatch/compose.yaml)
export TF_SKYWATCH_API_PORT="${TF_SKYWATCH_API_PORT:-18000}"
export TF_SKYWATCH_FIXTURE_PORT="${TF_SKYWATCH_FIXTURE_PORT:-18080}"
export API_BASE_URL="http://127.0.0.1:$TF_SKYWATCH_API_PORT"
export FIXTURE_URL="http://127.0.0.1:$TF_SKYWATCH_FIXTURE_PORT"
REPORT_DIR="${TESTFORGE_PHASE1_REPORT_DIR:-reports/skywatch/phase-one/$PROJECT}"
mkdir -p "$REPORT_DIR"
cleanup() {
  "${COMPOSE[@]}" logs --no-color > "$REPORT_DIR/starter.log" 2>&1 || true
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
result=0
if ! "$PYTHON" -m pytest tests/core -q --junitxml="$REPORT_DIR/core.xml"; then
  result=1
elif ! "$PYTHON" scripts/verify-junit.py "$REPORT_DIR/core.xml"; then
  result=1
fi
if ! "${COMPOSE[@]}" up --build -d --wait; then
  result=1
elif ! "$PYTHON" -m pytest tests/skywatch/api -v --junitxml="$REPORT_DIR/api.xml"; then
  result=1
elif ! "$PYTHON" scripts/verify-junit.py "$REPORT_DIR/api.xml"; then
  result=1
fi
cleanup
trap - EXIT
if ! TESTFORGE_REPORT_DIR="$REPORT_DIR/isolated" bash scripts/run-skywatch-isolated.sh; then
  result=1
fi
if ! TESTFORGE_DEMO_REPORT_DIR="$REPORT_DIR/regression-demo" bash scripts/demo-regression.sh; then
  result=1
fi
echo "Phase 1 reports: $REPORT_DIR"
exit "$result"
