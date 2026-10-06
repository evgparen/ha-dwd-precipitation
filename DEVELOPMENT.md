# Development guide

Read FORK.md for the current behavior and release policy.

One BaseProductUpdateCoordinator per DWD product owns scheduling, cache lifetime,
retry and metadata. Products implement `_fetch_and_parse`. Entity availability
is derived from the original release deadline, never the latest retry timestamp.

Run `python -m pytest tests/integration tests/parser` in the HA test environment.
Run live source checks separately, without the HA plugin's DNS isolation.
Do not change entity unique IDs or site-specific automations in this repository.
Retain the Apache-2.0 license and embedded wradlib/parser attribution.
