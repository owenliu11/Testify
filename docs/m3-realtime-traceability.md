# M3 real-time and browser coverage

Every scenario runs against a fresh Compose project, database, Redis, API process, and synthetic provider. Browser tests additionally run the built frontend through Vite preview. Map tiles are served from a local blank fixture; aircraft, HTTP, history, and WebSocket behavior are real.

| Case | Behavior and evidence |
| --- | --- |
| WS-01 | Snapshot carries the expected fields, synthetic aircraft, and zero ground speed. |
| WS-02 | An initially empty viewport receives an aircraft entry, a position update, and a leave event, with increasing sequence numbers. |
| WS-03 | A reconnecting client receives a fresh snapshot. |
| WS-04 | An aircraft near the 60-second freshness boundary is evicted and generates a leave event. |
| UI-01 | A stationary synthetic aircraft is selected on the WebGL canvas; its identity, units, and committed history are displayed. |
| UI-02 | A completed empty provider cycle produces the connected empty view. |
| UI-03 | Stopping the API closes the real socket and clears aircraft; restarting it and ingesting a new cycle restores the view. |

The isolated runner writes per-scenario JUnit XML and Compose logs under `reports/skywatch/isolated/<project>/`. Browser failures also retain screenshots and Playwright traces under that run's `browser/` directory; CI uploads the reports directory even after a failure. Browser tests use a fixed viewport and check WebGL before interacting with the map.

The SkyWatch frontend's existing Vite configuration proxies API paths in development mode only. The test-only container adds equivalent proxy settings for Vite preview while building an otherwise unchanged checkout. The original upstream project files are not modified.
