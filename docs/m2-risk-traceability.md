# M2 risk traceability

Each integration case must run in a fresh Compose project or a separately reset serial group. `scripts/run-skywatch-isolated.sh` creates and destroys a dedicated project for each collected integration or timestamp regression case; use unique ports for concurrent runs. It saves JUnit and Compose logs under `reports/skywatch/isolated/`.

| ID | Risk | Evidence |
| --- | --- | --- |
| CORE-01–11 | Bad configuration, leaked headers, client failures, unbounded waits, malformed output | `tests/core/test_core.py`, no services required |
| API-01–09 | API health, response shape, bbox and limit validation, missing aircraft, nullable values, track boundaries/truncation, and anomaly response | `tests/skywatch/api/test_contracts.py` |
| INT-01 | Synthetic provider observation fails to reach live and committed history | `tests/skywatch/integration/test_ingestion.py` |
| INT-02 | Duplicate observations roll back live state or duplicate committed history | `test_int_02_duplicate_does_not_duplicate_history_or_rollback` |
| INT-03 | Empty provider results fail or aircraft fail to expire | `test_int_03_empty_cycles_and_eviction` covers null and empty lists |
| INT-04 | A malformed row discards valid data | `test_int_04_malformed_row_does_not_discard_valid_row` |
| INT-05 | Provider errors or invalid JSON produce fabricated data or prevent recovery | `test_int_05_upstream_failure_then_recovery` |
| INT-06 | 401 refresh causes missing or unbounded retries | `test_int_06_unauthorized_refresh_retries_once` |
| INT-07 | Invalid aircraft timestamp kills WebSocket broadcaster | `tests/skywatch/regression/test_timestamps.py` |
| INT-08 | Invalid snapshot timestamp kills continuous polling | `tests/skywatch/regression/test_timestamps.py` |
| OUTAGE-01–02 | Database or Redis failure goes unreported and does not recover | `tests/skywatch/outages/test_dependency_outages.py`; each dependency gets a dedicated stack |

## Timestamp defects

Against SkyWatch `413a8237fdcf9afeaa9e495f9e6e96c720bcf18f`, INT-07 timed out waiting for a snapshot after an out-of-range `last_contact`; INT-08 timed out after only one provider request in continuous-polling mode. Dependency health alone remained insufficient evidence that the background tasks were alive. Both defects' captured evidence is under ignored `reports/skywatch/defects/` on the machine where they were reproduced.

The fix validates row timestamps and snapshot timestamps at parsing/model boundaries. An invalid row is rejected without discarding valid rows; an invalid snapshot is returned as a failed provider result so the scheduler can retry. The fix was merged and tagged in SkyWatch `v0.4.1`; TestForge pins release commit `e83e675a66fa7cf8e00a1b28397be1f08a662832`.

The outage checks verify health reporting and dependency reconnection. They do not prove lossless ingestion: SkyWatch can drop historical writes under queue pressure, and restarting the API clears its live in-memory state. Populated anomaly filtering remains to be verified.
