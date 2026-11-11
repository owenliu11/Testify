#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PYTHON="${TESTFORGE_PYTHON:-.venv/bin/python}"
: "${AGENTFORGE_DIR:?Set AGENTFORGE_DIR to the pinned AgentForge checkout}"
if [ "$(git -C "$AGENTFORGE_DIR" rev-parse HEAD)" != "84b1c95aaa98c5855ab627aff141cdf12cac8da4" ] || [ -n "$(git -C "$AGENTFORGE_DIR" status --porcelain)" ]; then
  echo "AgentForge must be clean and at the pinned commit 84b1c95" >&2
  exit 1
fi
export TESTFORGE_AGENT_PROJECT="tf_agent_$$"
COMPOSE=(docker compose -p "$TESTFORGE_AGENT_PROJECT" -f targets/agentforge/compose.yaml)
export TF_API_PORT="${TF_API_PORT:-18010}" TF_EFFECTS_PORT="${TF_EFFECTS_PORT:-18011}"
export AGENTFORGE_API_URL="http://127.0.0.1:$TF_API_PORT" AGENTFORGE_EFFECTS_URL="http://127.0.0.1:$TF_EFFECTS_PORT"
REPORT_DIR="${TESTFORGE_REPORT_DIR:-reports/agentforge/isolated/$TESTFORGE_AGENT_PROJECT}"
mkdir -p "$REPORT_DIR"
NODES="$(mktemp)"
cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$NODES"
}
trap cleanup EXIT
if [ "$#" -eq 0 ]; then set -- tests/agentforge; fi
if ! "$PYTHON" -m pytest --collect-only -q "$@" > "$NODES.raw"; then
  cat "$NODES.raw" >&2
  rm -f "$NODES.raw"
  exit 1
fi
sed -n '/::/p' "$NODES.raw" > "$NODES"
rm -f "$NODES.raw"
if [ ! -s "$NODES" ]; then echo "No scenarios collected" >&2; exit 1; fi
result=0
index=0
while IFS= read -r node; do
  index=$((index + 1))
  export TESTFORGE_EVIDENCE_DIR="$REPORT_DIR/evidence/$index"
  mkdir -p "$TESTFORGE_EVIDENCE_DIR"
  echo "Running isolated scenario: $node"
  if [[ "$node" == *test_recovery.py* ]]; then
    "${COMPOSE[@]}" up --build -d --wait --wait-timeout 120 db mock_effects api
  else
    "${COMPOSE[@]}" up --build -d --wait --wait-timeout 120
  fi
  if [ "$?" -ne 0 ]; then
    result=1
  elif ! "$PYTHON" -m pytest "$node" -v --junitxml="$REPORT_DIR/$index.xml"; then
    result=1
  elif ! "$PYTHON" scripts/verify-junit.py "$REPORT_DIR/$index.xml"; then
    result=1
  fi
  "$PYTHON" scripts/capture-agentforge.py || true
  "${COMPOSE[@]}" logs --no-color > "$REPORT_DIR/$index.log" 2>&1 || true
  "${COMPOSE[@]}" down -v --remove-orphans || result=1
done < "$NODES"
exit "$result"
