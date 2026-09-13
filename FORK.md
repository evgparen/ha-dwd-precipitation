# Maintained DWD Precipitation fork

Release 2026.9.13.1, maintained at https://github.com/evgparen/ha-dwd-precipitation. Upstream is
https://github.com/Hoffmann77/ha-dwd-precipitation, based on commit
`9d6f0098df53edf20ec0478c0aa7dd6ea5a04a55` (2026.8.0rc1).
The original Apache-2.0 license and embedded parser attribution are retained.

## Bounded cache (2026.9.13.1)

RS, RV and HymecNG keep their last successful product for **five extra minutes**
after the previous stale boundary. This is a fixed deadline based on the source
release, never on the last request, error, or state update. A dedicated timer
expires the cache at that deadline even if a network request is still pending.
Minute retries continue through expiration; startup without data stays unavailable.
Hourly/daily products retain their prior age limits.

With default options, maximum age from the release is 14m10s for RS/RV and 13m
for HymecNG. RV lead-0 window starts five minutes before its release; consumers
using that start timestamp must account for that difference. Source payloads and
forecast timestamps are never changed on cache reuse. The explicit user option
to disable stale protection remains supported and is labelled expired after the
normal deadline, rather than presenting the data as current.

Sensor and binary-sensor attributes always include `dwd_fetch`: status
(`current`, `cached`, `expired`, `unavailable`), source_release,
source_age_seconds (snapshot when the entity is written), valid_until,
last_attempt, and error. Use the absolute source/deadline for automation age
checks. This is diagnostic data, not proof of actual precipitation. The derived
dry-streak sensor retains its existing attributes. Three diagnostic entities (RS/RV/HymecNG data status) stay available even when
weather entities expire. No changes to thresholds, site automations, credentials
or existing IDs.

Tests cover repeated failures, fixed boundary, expiration during a pending
request, initial failure, successful recovery, disabled stale checking and
unload. A real HA integration/entity test checks on → cached → unavailable →
current with no device or network calls.

## First change (2026.9.12.1)

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

Validation on 2026-09-12:

- 63 parser tests passed.
- 76 integration tests and 5 subtests passed with Home Assistant 2026.9.1,
  including all 10 new retry regressions. The same integration tests also
  passed against the original HA 2026.8.0 dependency set.
- 4 comparisons against wradlib passed.
- 5 live DWD download/parser tests passed: RS, RV (all 25 members), HymecNG,
  RW and SF. Live tests prove source/parser access, not forecast accuracy.

Inherited NumPy deprecation and the HA-free pytest tier's unused asyncio option
produce warnings, not failures. This is not a guarantee against future HA/DWD
changes or incorrect weather forecasts.

## Installation and updates

The component uses the existing domain `dwd_precipitation` and preserves unique
IDs and configuration. It replaces an existing installation; do not install two
implementations of this domain side by side.

1. Back up the component and site configuration; record entity IDs and options.
2. Add `https://github.com/evgparen/ha-dwd-precipitation` as a HACS custom
   integration repository.
3. For a migration, uninstall the upstream repository in HACS, then immediately
   download this fork's release. Keep the DWD integration/config entry itself.
4. Check the Home Assistant configuration and restart Home Assistant Core.
5. Verify the loaded version, config entry, all existing entity IDs, fresh source
   timestamps, and the site's dependent automation. Check logs after startup.

HACS should show only the fork installed for this domain. Roll back by restoring
its predecessor's component directory and restarting Core, then repair the HACS
installation source to match. Restore unrelated config/registries only if needed.

Future upstream changes are reviewed and merged into this fork before release;
site updates follow the fork's own release tags. GitHub Actions remains disabled
for this fork: the publishing credential has repository access but no workflow
scope. Inherited workflow files are unchanged. The release was validated locally
with all test tiers; future workflow changes require an appropriately scoped
credential. No inherited scheduled issue-posting job runs in this fork.

Site-specific rain closure schedules, stored plans, entity names, credentials,
and site coordinates belong in each installation, not in this reusable source.

Validation for 2026.9.13.1: 153 integration/parser tests plus 5 subtests passed
with Home Assistant 2026.9.1. The integration tier includes 14 new bounded-cache
cases and the extended real HA lifecycle test. Live downloads run separately
from the HA test plugin, which deliberately disables external DNS.

All five live DWD download/parser checks (RS, RV, HymecNG, RW, SF) also passed.
