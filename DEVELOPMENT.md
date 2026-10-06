# Development guide

This fork is no longer maintained as of 2026-10-06. Do not continue feature work
or plan further upstream merges here. Development is focused on the separate
Wolkenwart Regenradar project. Read FORK.md for the final release and historical
validation details.

One BaseProductUpdateCoordinator per DWD product owns scheduling, cache lifetime,
retry and metadata. Products implement `_fetch_and_parse`. Entity availability
is derived from the original release deadline, never the latest retry timestamp.

Run `python -m pytest tests/integration tests/parser` in the HA test environment.
Run live source checks separately, without the HA plugin's DNS isolation.
Do not change entity unique IDs or site-specific automations in this repository.
Retain the Apache-2.0 license and embedded wradlib/parser attribution.
