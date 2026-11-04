# rd_machine_sms — independent changelog

This file records only changes to `rd_machine_sms`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `rd_machine_sms` compiled-plugin at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `hybrid_bank2_parity; hybrid_input_parity`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `harness`. No independently validated video/PSG/IRQ gameplay parity; production engine has separate implementation.
