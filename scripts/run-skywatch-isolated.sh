#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PYTHON="${TESTFORGE_PYTHON:-.venv/bin/python}"
PROJECT="tf_m2_$$"
export TESTFORGE_COMPOSE_PROJECT="$PROJECT"
COMPOSE=(docker compose -p "$PROJECT" -f targets/skywatch/compose.yaml)
export TF_SKYWATCH_API_PORT="${TF_SKYWATCH_API_PORT:-18000}"
export TF_SKYWATCH_FIXTURE_PORT="${TF_SKYWATCH_FIXTURE_PORT:-18080}"
export API_BASE_URL="http://127.0.0.1:$TF_SKYWATCH_API_PORT"
export FIXTURE_URL="http://127.0.0.1:$TF_SKYWATCH_FIXTURE_PORT"
export WS_URL="ws://127.0.0.1:$TF_SKYWATCH_API_PORT/ws/live"
REPORT_DIR="${TESTFORGE_REPORT_DIR:-reports/skywatch/isolated/$PROJECT}"
mkdir -p "$REPORT_DIR"
NODES="$(mktemp)"
cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$NODES"
}
trap cleanup EXIT
if [ "$#" -eq 0 ]; then
  set -- tests/skywatch/integration tests/skywatch/regression tests/skywatch/outages
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
  export SKYWATCH_TEST_MODE=true FIXTURE_SCENARIO=normal
  case "$node" in
    *test_int_08*) export SKYWATCH_TEST_MODE=false FIXTURE_SCENARIO=bad_snapshot ;;
  esac
  echo "Running isolated scenario: $node"
  if ! "${COMPOSE[@]}" up --build -d --wait; then
    result=1
  elif ! "$PYTHON" -m pytest "$node" -v --junitxml="$REPORT_DIR/$index.xml"; then
    result=1
  fi
  "${COMPOSE[@]}" logs --no-color > "$REPORT_DIR/$index.log" 2>&1 || true
  "${COMPOSE[@]}" down -v --remove-orphans || result=1
done < "$NODES"
exit "$result"
