# Pre-build / architectural approval — v0.4.9.18

**Date:** 2026-11-07. **Owner approval:** Explicit request "build it then please" after reviewing the proposed three fixes in the v0.4.9.17 diagnostic analysis. The promoted GitHub main is `ab8745242c81e5e6cbb5754bac0d3710f289e4bc`, tag `workspace/v0.4.9.17`.

## Scoped implementation

1. Fix controller's diagnostic destination independently from old job paths. Use `C:\Projects\RecompDev-Evidence/v0.4.9.18` for new jobs and ZIPs when the owner's existing configured `--workspace` ends in `v0.4.9.17`; accept explicit `--evidence-root`. Preserve AppData configuration and read-only old job discovery.
2. Include source-matched, bounded, address-only coverage deltas and PC/mapper stop context in compact upload archives, with strict privacy rules and no original ROM/compiled project content.
3. Avoid unchanged Ghidra/Rizin reruns only when original ROM SHA/size, tool hashes/paths, maintained source/Java scripts and analysis artifacts are reverified. Continue reattesting cumulative history and prioritise newest genuine stop evidence. No CPU/hardware/game-title logic in the controller.
4. Permit a one-ZIP development checkpoint from the already promoted exact `main` baseline without requiring a nonexistent dev/v17 branch. Source-only `Install` continues under the previously approved infrastructure policy; full tests and rollback remain mandatory.

## Acceptance and constraints

Linux C++ build, Python/cache/privacy/CLI/Git tests, source-hash package manifest, unchanged 642-file historic trees and complete Windows MSVC/CTest must pass before `Install`. The active production binaries and runtime lockfile remain untouched. No fabricated 1,800-frame results, original-ROM independence, second-ROM verification, compiled analysis ABI, or behavioral parity claims. This is infrastructure only and GitHub push remains manual. Legacy migration register stays accountable.
