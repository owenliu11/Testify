"""Browser journeys use the real frontend, WebSocket, API, and synthetic provider."""

import math
import os
import re
import subprocess
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect

from testforge.wait import wait_for

API = os.getenv("API_BASE_URL", "http://127.0.0.1:18000")
FIXTURE = os.getenv("FIXTURE_URL", "http://127.0.0.1:18080")
UI = os.getenv("UI_BASE_URL", "http://127.0.0.1:15173")
TILE = (Path(__file__).parents[3] / "fixtures/skywatch/blank-tile.png").read_bytes()


@pytest.fixture(autouse=True)
def offline_map(page):
    page.route("https://tile.openstreetmap.org/**", lambda route: route.fulfill(status=200, content_type="image/png", body=TILE))


def cycle(scenario):
    httpx.post(f"{FIXTURE}/scenario", json={"scenario": scenario}, timeout=5).raise_for_status()
    response = httpx.post(f"{API}/__test/ingest/cycles", json={"scenario_id": scenario}, timeout=30)
    response.raise_for_status()
    assert response.json()["status"] == "succeeded", response.text


def ready(page):
    page.goto(UI, wait_until="domcontentloaded")
    expect(page.get_by_role("status").filter(has_text="WebSocket · connected")).to_be_visible(timeout=30000)
    canvas = page.locator("canvas.maplibregl-canvas")
    expect(canvas).to_be_visible(timeout=30000)
    version = canvas.evaluate("c => { const gl = c.getContext('webgl2'); return gl && gl.getParameter(gl.VERSION); }")
    assert version and "WebGL" in version, f"WebGL map unavailable: {version!r}"
    return canvas


def visible_count(page):
    return page.get_by_label("Aircraft in the current viewport").locator("div").filter(has_text="Visible aircraft").locator("dd")


def position(canvas, lon, lat):
    box = canvas.bounding_box()
    assert box
    scale = 512 * 2**5.5
    def mercator_y(latitude):
        sine = math.sin(math.radians(latitude))
        return (1 - math.log((1 + sine) / (1 - sine)) / (2 * math.pi)) / 2
    return (box["x"] + box["width"] / 2 + (lon + 119.5) / 360 * scale,
            box["y"] + box["height"] / 2 + (mercator_y(lat) - mercator_y(36.8)) * scale)


def test_ui_01_aircraft_details_and_history(page):
    cycle("stationary")
    wait_for(lambda: httpx.get(f"{API}/aircraft/abc123/track", timeout=5).json()["count"] > 0, "committed track")
    canvas = ready(page)
    expect(visible_count(page)).to_have_text("1", timeout=20000)
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    x, y = position(canvas, -122.3, 37.6)
    page.mouse.click(x, y)
    expect(page.get_by_role("heading", name="TEST123")).to_be_visible(timeout=10000)
    expect(page.get_by_text("ICAO24 · ABC123")).to_be_visible()
    expect(page.get_by_text("10,000 m", exact=True)).to_be_visible()
    expect(page.get_by_text("0 m/s", exact=True)).to_be_visible()
    expect(page.get_by_text("Only one recent position available; showing its marker.")).to_be_visible(timeout=10000)
    page.get_by_role("button", name="Close aircraft details").click()
    expect(page.get_by_role("heading", name="TEST123")).not_to_be_visible()


def test_ui_02_completed_empty_view(page):
    cycle("empty_null")
    ready(page)
    expect(visible_count(page)).to_have_text("0", timeout=20000)
    expect(page.get_by_text("No aircraft in this view.", exact=False)).to_be_visible(timeout=20000)


def test_ui_03_disconnect_and_recover(page):
    project = os.getenv("TESTFORGE_COMPOSE_PROJECT", "")
    if not re.fullmatch(r"tf_m2_[0-9]+", project):
        pytest.fail("Run browser recovery test with scripts/run-skywatch-isolated.sh")
    compose = ["docker", "compose", "-p", project, "-f", "targets/skywatch/compose.yaml"]
    cycle("stationary")
    closed = []
    page.on("websocket", lambda ws: ws.on("close", lambda _ws: closed.append(True)))
    ready(page)
    expect(visible_count(page)).to_have_text("1", timeout=20000)
    try:
        subprocess.run([*compose, "stop", "api"], check=True, timeout=30)
        page.wait_for_function("() => !document.querySelector('.connection-connected')", timeout=15000)
        assert closed, "The original WebSocket did not close"
        expect(visible_count(page)).to_have_text("0", timeout=10000)
    finally:
        subprocess.run([*compose, "start", "api"], check=True, timeout=30)
    expect(page.get_by_role("status").filter(has_text="WebSocket · connected")).to_be_visible(timeout=45000)
    cycle("stationary")
    expect(visible_count(page)).to_have_text("1", timeout=20000)
