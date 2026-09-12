# Maintained DWD Precipitation fork

Development snapshot started 2026-09-12. Upstream is
https://github.com/Hoffmann77/ha-dwd-precipitation, based on commit
`9d6f0098df53edf20ec0478c0aa7dd6ea5a04a55` (2026.8.0rc1).
The original Apache-2.0 license and embedded parser attribution are retained.

## First change

A request just after the next release boundary already considers the previous
cached release stale. The original stale-error path cancels its minute retry.
If files consistently appear seconds after the scheduled request, every
five-minute request selects another not-yet-available file. This can leave
entities unavailable for hours even though the historical file series is complete.

This fork keeps the existing 60-second retry active on initial and stale errors.
Successful fetches and entry unload still cancel it. Failed requests never renew
the cached source timestamp. The stale-data option, product parsing, entity IDs,
and normal event-driven update schedule are preserved. HTTP 404 is reported as
a failed request without assuming why the file was unavailable.

## Verification

`tests/integration/test_retry_regression.py` covers a late-file recovery, first
failure at the staleness boundary, connection/404/503/timeout/parser failures,
startup, an hour-long outage, fresh cache, the explicit stale option,
cancellation, and timer cleanup. It runs with real Home Assistant imports in an
isolated Python process, without network or actuator calls:

```sh
PYTHONPATH=. python tests/integration/test_retry_regression.py
```

Validation on 2026-09-12: all 10 new regression tests passed in an isolated
Python process using the Home Assistant 2026.9.1 container environment. The
staged source was imported from a temporary directory, not from live /config.

The upstream pytest tiers remain available via the dependency groups in
`pyproject.toml`. A focused regression pass is not a full HA reload, parser,
or long-term field certification. Upstream code and existing tests may contain
other defects; this fork makes no promise of being error-free.

## Release and installation status

This is a separate local development branch, not a published GitHub fork or a
production release. The manifest remains at the upstream version until a release
is prepared. There is no new deployment as part of creating this branch.
Existing HA installations retain their current code and configuration.

Before distribution, assign a distinct fork version and maintainer/support
metadata, run the full relevant test tiers and HA config/reload checks, prepare a
rollback artifact, then switch the installation source. Never manage two HACS
repositories for the same `dwd_precipitation` domain simultaneously.
Check future upstream updates before merging them into this branch.

Site-specific rain closure schedules, stored plans, entity names, credentials,
and site coordinates belong in each installation, not in this reusable source.
