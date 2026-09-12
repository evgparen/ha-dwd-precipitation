# 2026.9.12.1

A DWD file arriving seconds after the scheduled request could leave sensors
unavailable until the next five-minute cycle. Repeated publication delays could
extend this to hours. The fork retains the existing 60-second retry on initial
and stale failures while keeping source-age protection active. HTTP 404 messages
now report the response without asserting that the DWD never published a file.

Existing domain, sensor unique IDs, options and normal update schedules are
preserved. No site-specific automation is included. Fork maintainer/version/links
are separate from upstream; Apache-2.0 and embedded parser attribution retained.

Validation: 63 parser tests, 76 HA integration tests plus 5 subtests, 4 wradlib
comparisons, and 5 real DWD source tests passed. HA integration tests passed on
2026.8.0 and the deployment target 2026.9.1. No actuator calls were used.
See FORK.md for migration and rollback steps.
