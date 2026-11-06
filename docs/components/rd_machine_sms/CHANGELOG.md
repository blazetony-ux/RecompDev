# rd_machine_sms — independent changelog

## [0.2.0] - 2026-11-05

- **Changed:** Conservative static-ROM reset/interrupt source mapping with dynamic/banked addresses remaining unresolved.
- **Validation:** Linux CMake/CTest native discovery contract and existing harness regressions; full Windows and real-ROM translation/build remain acceptance gates.
- **Compatibility:** New `rd_sms_resolve_source_v1` extension; runtime bus ABI remains unchanged.

This file records only changes to `rd_machine_sms`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `rd_machine_sms` compiled-plugin at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `hybrid_bank2_parity; hybrid_input_parity`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `harness`. No independently validated video/PSG/IRQ gameplay parity; production engine has separate implementation.
