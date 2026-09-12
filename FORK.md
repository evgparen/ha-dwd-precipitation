# Maintained DWD Precipitation fork

Release 2026.9.12.1, maintained at https://github.com/evgparen/ha-dwd-precipitation. Upstream is
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
