# 2026.10.6.1

Integrates upstream 2026.9.1 improvements while retaining reliable rain-protection
retries and explicit cache diagnostics.

- Independent, parallel product startup; failed setup timers are cleaned up.
- Correct local-day/DST scheduling and stable fetch offsets to spread DWD load.
- Source-based expiry is armed on every successful fetch and enforced at the
  exact boundary, including pending requests.
- RS/RV/HymecNG retries remain at 60 seconds; hourly/daily retries use backoff.
- Existing diagnostic and weather IDs preserved; German translations added.
- Radar grace is now six minutes after the next release is due. Automations'
  stricter source-age limits remain independent. No site settings are changed.

Validation: 184 HA integration/parser tests and 5 live DWD source/parser checks
passed. No actuator calls. See FORK.md for behavior, migration and rollback.
