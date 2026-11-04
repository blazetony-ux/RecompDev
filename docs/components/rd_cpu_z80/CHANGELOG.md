# rd_cpu_z80 — independent changelog

This file records only changes to `rd_cpu_z80`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `rd_cpu_z80` compiled-plugin at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `unsupported_opcode_rejected; hybrid_main_parity; native_only_single_block`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `harness`. Not a complete Z80 interpreter; not used in production Shinobi translation.
