#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PYTHON="${TESTFORGE_PYTHON:-.venv/bin/python}"
PROJECT="tf_m2_$$"
export TESTFORGE_COMPOSE_PROJECT="$PROJECT"
COMPOSE=(docker compose -p "$PROJECT" -f targets/skywatch/compose.yaml)
export TF_SKYWATCH_API_PORT="${TF_SKYWATCH_API_PORT:-18000}"
export TF_SKYWATCH_FIXTURE_PORT="${TF_SKYWATCH_FIXTURE_PORT:-18080}"
export TF_SKYWATCH_UI_PORT="${TF_SKYWATCH_UI_PORT:-15173}"
export API_BASE_URL="http://127.0.0.1:$TF_SKYWATCH_API_PORT"
export FIXTURE_URL="http://127.0.0.1:$TF_SKYWATCH_FIXTURE_PORT"
export WS_URL="ws://127.0.0.1:$TF_SKYWATCH_API_PORT/ws/live"
export UI_BASE_URL="http://127.0.0.1:$TF_SKYWATCH_UI_PORT"
REPORT_DIR="${TESTFORGE_REPORT_DIR:-reports/skywatch/isolated/$PROJECT}"
mkdir -p "$REPORT_DIR"
NODES="$(mktemp)"
cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$NODES"
}
trap cleanup EXIT
if [ "$#" -eq 0 ]; then
  set -- tests/skywatch/integration tests/skywatch/regression tests/skywatch/outages tests/skywatch/ws tests/skywatch/ui
fi
if ! "$PYTHON" -m pytest --collect-only -q "$@" | sed -n '/::/p' > "$NODES"; then
  echo "Could not collect scenarios" >&2
  exit 1
fi
if [ ! -s "$NODES" ]; then
  echo "No scenarios collected" >&2
  exit 1
fi
result=0
index=0
while IFS= read -r node; do
  index=$((index + 1))
  export TESTFORGE_EVIDENCE_DIR="$REPORT_DIR/evidence/$index"
  export SKYWATCH_TEST_MODE=true FIXTURE_SCENARIO=normal
  COMPOSE=(docker compose -p "$PROJECT" -f targets/skywatch/compose.yaml)
  PYTEST_ARGS=(--screenshot=only-on-failure --tracing=retain-on-failure --output="$REPORT_DIR/browser/$index")
  case "$node" in
    *test_int_08*) export SKYWATCH_TEST_MODE=false FIXTURE_SCENARIO=bad_snapshot ;;
    *tests/skywatch/ui/*)
      COMPOSE=(docker compose -p "$PROJECT" --profile ui -f targets/skywatch/compose.yaml)
      if [ -n "${TESTFORGE_BROWSER_CHANNEL:-}" ]; then
        PYTEST_ARGS+=(--browser-channel="$TESTFORGE_BROWSER_CHANNEL")
      fi ;;
  esac
  echo "Running isolated scenario: $node"
  if ! "${COMPOSE[@]}" up --build -d --wait; then
    result=1
  elif ! "$PYTHON" -m pytest "$node" -v "${PYTEST_ARGS[@]}" --junitxml="$REPORT_DIR/$index.xml"; then
    result=1
  elif ! "$PYTHON" scripts/verify-junit.py "$REPORT_DIR/$index.xml"; then
    result=1
  fi
  "$PYTHON" scripts/capture-skywatch.py || true
  "${COMPOSE[@]}" logs --no-color > "$REPORT_DIR/$index.log" 2>&1 || true
  "${COMPOSE[@]}" down -v --remove-orphans || result=1
done < "$NODES"
echo "SkyWatch reports: $REPORT_DIR"
exit "$result"
