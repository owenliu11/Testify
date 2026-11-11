"""Fail an acceptance run that collected no tests or silently skipped any."""

import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
counts = {key: sum(int(suite.get(key, 0)) for suite in suites) for key in ("tests", "errors", "failures", "skipped")}
if counts["tests"] < 1 or any(counts[key] for key in ("errors", "failures", "skipped")):
    raise SystemExit(f"Invalid acceptance result: {counts}")
print(f"Acceptance result: {counts}")
