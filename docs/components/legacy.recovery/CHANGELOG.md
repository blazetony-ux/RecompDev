# legacy.recovery — independent changelog

This file records only changes to `legacy.recovery`. Component versioning is independent of workspace release tags.

## [0.4.0.45] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `legacy.recovery` legacy-service at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `migration_legacy_regressions; v042_recovery_manager`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `production-workflow`. Production recovery uses its own Python/native engine, not the harness DLLs.
