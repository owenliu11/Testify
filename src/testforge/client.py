"""HTTP client lifetime and safe diagnostics."""

from collections.abc import Mapping

import httpx

SENSITIVE = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {key: "[REDACTED]" if key.lower() in SENSITIVE else value for key, value in headers.items()}


def http_client(base_url: str, timeout: float) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=timeout, trust_env=False)
