"""Bounded polling without silently swallowing assertion failures."""

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def wait_for(check: Callable[[], T], what: str, deadline_s: float = 45, interval_s: float = 0.25, retry_on: tuple[type[Exception], ...] = ()) -> T:
    if deadline_s <= 0 or interval_s <= 0:
        raise ValueError("deadline and interval must be positive")
    deadline = time.monotonic() + deadline_s
    last: object = None
    while True:
        try:
            last = check()
            if last:
                return last
        except retry_on as exc:
            last = exc
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for {what}. Last result: {last!r}")
        time.sleep(min(interval_s, remaining))
