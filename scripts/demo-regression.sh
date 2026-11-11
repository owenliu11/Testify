#!/usr/bin/env bash
# Demonstrates an intentional, isolated missing-leave bug; never changes the source checkout.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
SOURCE="${SKYWATCH_DIR:-$HOME/skywatch}"
PYTHON="${TESTFORGE_PYTHON:-.venv/bin/python}"
REVISION="e83e675a66fa7cf8e00a1b28397be1f08a662832"
REPORT_DIR="${TESTFORGE_DEMO_REPORT_DIR:-reports/skywatch/regression-demo/$(date -u +%Y%m%dT%H%M%SZ)-$$}"
if [ -e "$REPORT_DIR" ]; then
  echo "Refusing to overwrite existing evidence: $REPORT_DIR" >&2
  exit 1
fi
mkdir -p "$REPORT_DIR"
REPORT_DIR="$(cd "$REPORT_DIR" && pwd -P)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT
if ! git clone --quiet --no-hardlinks --no-checkout "$SOURCE" "$TEMP_DIR/skywatch"; then exit 1; fi
if ! git -C "$TEMP_DIR/skywatch" checkout --quiet -b demo/drop-leave-events "$REVISION"; then exit 1; fi
"$PYTHON" - "$TEMP_DIR/skywatch/backend/app/api/ws.py" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
old = "    leave = sorted(previous_ids - current_ids)"
if text.count(old) != 1:
    raise SystemExit("Expected leave-event implementation not found exactly once")
path.write_text(text.replace(old, "    leave = []  # Intentional M4 regression demonstration"))
PY
if [ "$?" -ne 0 ]; then exit 1; fi
NODE=tests/skywatch/ws/test_live.py::test_ws_02_enter_update_and_leave
echo "Running the intentionally broken disposable branch; failure is expected."
if SKYWATCH_DIR="$TEMP_DIR/skywatch" TESTFORGE_REPORT_DIR="$REPORT_DIR/broken" bash scripts/run-skywatch-isolated.sh "$NODE" > "$REPORT_DIR/broken-run.log" 2>&1; then
  echo "Regression unexpectedly passed" >&2
  exit 1
fi
if ! "$PYTHON" scripts/verify-regression.py "$REPORT_DIR/broken"; then exit 1; fi
git -C "$TEMP_DIR/skywatch" restore backend/app/api/ws.py || exit 1
git -C "$TEMP_DIR/skywatch" diff --exit-code || exit 1
echo "Running the restored pinned source; success is expected."
if ! SKYWATCH_DIR="$TEMP_DIR/skywatch" TESTFORGE_REPORT_DIR="$REPORT_DIR/restored" bash scripts/run-skywatch-isolated.sh "$NODE" > "$REPORT_DIR/restored-run.log" 2>&1; then
  echo "Restored test failed; see $REPORT_DIR/restored-run.log" >&2
  exit 1
fi
printf 'Pinned SkyWatch revision: %s\nIntentional branch: demo/drop-leave-events\nBroken run: intended WS-02 missing-leave failure\nRestored run: passed\n' "$REVISION" > "$REPORT_DIR/summary.txt"
echo "Regression demonstration passed. Evidence: $REPORT_DIR"
